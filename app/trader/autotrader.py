"""
autotrader.py — Signal-driven auto-execution engine

Monitors the signal pipeline and fires trades when criteria are met.
Calls into jupiter.py for execution and positions.py for tracking.
"""

import asyncio
import logging
import random
import time
from typing import Optional
from solders.keypair import Keypair
import base58

from .wallet import get_private_key, get_wallet_info, is_trading_enabled
from .jupiter import buy_token, sell_token, get_sol_balance, get_mint
from .positions import Position, PositionMonitor, add_position, close_position, get_user_positions

logger = logging.getLogger(__name__)

# ── Signal criteria constants ─────────────────────────────────────────────────
DEFAULT_MIN_SAFETY    = 75
DEFAULT_MIN_ALPHA     = 0.68
DEFAULT_MIN_WALLETS   = 2
DEFAULT_SOL_PER_TRADE = 0.1    # SOL
DEFAULT_MAX_TRADES    = 3
DEFAULT_TP_PCT        = 50
DEFAULT_SL_PCT        = 30

# Tokens supported for auto-trading (have known mints)
TRADEABLE = {"BONK","WIF","POPCAT","MEW","BOME","SAMO","FARTCOIN","JUP"}


def keypair_from_bytes(key_bytes: bytes) -> Optional[Keypair]:
    """Load a Keypair from raw bytes (64-byte secret key)"""
    try:
        if len(key_bytes) == 64:
            return Keypair.from_bytes(key_bytes)
        elif len(key_bytes) == 32:
            return Keypair.from_seed(key_bytes)
        # Try base58 decode
        decoded = base58.b58decode(key_bytes)
        return Keypair.from_bytes(decoded)
    except Exception as e:
        logger.error(f"Keypair load error: {e}")
        return None


def evaluate_signal(signal: dict, settings: dict) -> tuple[bool, str]:
    """
    Decide whether to trade based on signal + user settings.
    Returns (should_trade, reason_string)
    """
    sym = signal.get("symbol", "").upper()
    
    if sym not in TRADEABLE:
        return False, f"{sym} not supported for auto-trading yet (no on-chain mint mapping)"

    if not get_mint(sym):
        return False, f"No mint address for {sym}"

    alpha  = signal.get("alpha_score", 0)
    safety = signal.get("safety_score", 0)
    wallets = signal.get("wallets_in", 0)
    trade_now = signal.get("trade_now", False)

    min_safety  = settings.get("min_safety_score", DEFAULT_MIN_SAFETY)
    min_alpha   = settings.get("min_alpha_score", DEFAULT_MIN_ALPHA)
    min_wallets = settings.get("min_wallets_in", DEFAULT_MIN_WALLETS)

    if not trade_now:
        return False, "Signal engine says WAIT"
    if safety < min_safety:
        return False, f"Safety {safety} < minimum {min_safety}"
    if alpha < min_alpha:
        return False, f"Alpha {alpha} < minimum {min_alpha}"
    if wallets < min_wallets:
        return False, f"Only {wallets} smart wallets in — need {min_wallets}+"

    return True, "All criteria passed ✅"


class AutoTrader:
    """
    The main auto-trader engine.
    Instantiated once per bot; handles all users' wallets.
    """

    def __init__(self, bot, notify_callback):
        self.bot = bot
        self.notify = notify_callback  # async (user_id, message) → send Telegram msg
        self.monitor = PositionMonitor(on_exit_needed=self._handle_exit)
        self._running = False
        self._scan_task = None
        # Track which tokens we've recently opened to avoid double-entry
        self._recent_entries: dict[str, float] = {}  # symbol → timestamp

    def start(self):
        self._running = True
        self.monitor.start()
        self._scan_task = asyncio.create_task(self._signal_scan_loop())
        logger.info("AutoTrader started")

    def stop(self):
        self._running = False
        self.monitor.stop()
        if self._scan_task:
            self._scan_task.cancel()

    # ── Signal scan loop ──────────────────────────────────────────────────────

    async def _signal_scan_loop(self):
        """Runs every 3 minutes, generates signals for top tokens, checks all users"""
        # Import here to avoid circular
        from ...bot import compute_safety_score, compute_signal, get_real_price
        
        WATCH_TOKENS = list(TRADEABLE)  # Scan all tradeable tokens

        while self._running:
            try:
                for sym in WATCH_TOKENS:
                    if not self._running:
                        break
                    
                    # Skip if we entered this token recently (within 30 min)
                    last_entry = self._recent_entries.get(sym, 0)
                    if time.time() - last_entry < 1800:
                        continue

                    price_data = await get_real_price(sym)
                    safety = compute_safety_score(sym, price_data)
                    signal = compute_signal(sym, price_data, safety)

                    # Only proceed if signal says trade
                    if not signal.get("trade_now"):
                        await asyncio.sleep(1)
                        continue

                    # Check all users who have auto-trading enabled
                    await self._evaluate_for_all_users(signal, price_data)
                    await asyncio.sleep(2)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Signal scan error: {e}")

            await asyncio.sleep(180)  # Scan every 3 minutes

    async def _evaluate_for_all_users(self, signal: dict, price_data: Optional[dict]):
        """Check signal against every connected+enabled user's criteria"""
        # Import wallet store
        from .wallet import _wallet_store

        for user_id, wallet_data in list(_wallet_store.items()):
            settings = wallet_data.get("settings", {})
            if not settings.get("enabled", False):
                continue

            # Check open trade count
            open_trades = get_user_positions(user_id, "open")
            max_trades = settings.get("max_open_trades", DEFAULT_MAX_TRADES)
            if len(open_trades) >= max_trades:
                continue

            # Check if already in this token
            if any(p.token_symbol == signal["symbol"] for p in open_trades):
                continue

            # Evaluate signal against this user's settings
            should_trade, reason = evaluate_signal(signal, settings)
            if not should_trade:
                continue

            # Execute!
            await self._execute_entry(user_id, signal, price_data, settings)

    # ── Execute Entry ─────────────────────────────────────────────────────────

    async def _execute_entry(self, user_id: int, signal: dict, price_data: Optional[dict], settings: dict):
        sym = signal["symbol"]
        sol_amount = settings.get("max_position_sol", DEFAULT_SOL_PER_TRADE)
        tp_pct = settings.get("tp_pct", DEFAULT_TP_PCT)
        sl_pct = settings.get("sl_pct", DEFAULT_SL_PCT)

        # Notify user we're attempting entry
        await self.notify(user_id,
            f"⚡ *AutoTrader* — Signal fired for *{sym}*\n\n"
            f"Safety: `{signal['safety_score']}/100` | Alpha: `{signal['alpha_score']}`\n"
            f"Smart wallets in: `{signal['wallets_in']}`\n"
            f"Attempting to buy `{sol_amount} SOL` of {sym}...\n\n"
            f"_{signal['agent_summary']}_"
        )

        # Get keypair
        key_bytes = get_private_key(user_id)
        if not key_bytes:
            await self.notify(user_id, "❌ Could not load wallet — aborting trade")
            return

        keypair = keypair_from_bytes(key_bytes)
        if not keypair:
            await self.notify(user_id, "❌ Invalid keypair — aborting trade")
            return

        # Check balance
        balance = await get_sol_balance(str(keypair.pubkey()))
        min_needed = sol_amount + 0.01  # +0.01 for fees
        if balance < min_needed:
            await self.notify(user_id,
                f"❌ Insufficient SOL balance\n"
                f"Need: `{min_needed:.3f} SOL` | Have: `{balance:.4f} SOL`"
            )
            return

        # Execute buy
        result = await buy_token(keypair, sym, sol_amount)

        if not result["success"]:
            await self.notify(user_id,
                f"❌ Trade failed for *{sym}*\n"
                f"Reason: `{result.get('error', 'Unknown error')}`"
            )
            return

        # Record position
        entry_price = price_data["price"] if price_data else 0.0
        pos = Position(
            user_id=user_id,
            token_symbol=sym,
            chain="solana",
            entry_price_usd=entry_price,
            sol_spent=sol_amount,
            tokens_held=result["tokens_received"],
            tp_pct=tp_pct,
            sl_pct=sl_pct,
            tx_hash=result["signature"],
        )
        key = add_position(pos)
        self._recent_entries[sym] = time.time()

        # Notify success
        await self.notify(user_id,
            f"✅ *Position Opened — {sym}*\n\n"
            f"💰 Spent: `{sol_amount} SOL`\n"
            f"🪙 Received: `{result['tokens_received']:,} {sym}`\n"
            f"📈 Entry price: `${entry_price:.8f}`\n"
            f"🎯 Take profit: `+{tp_pct}%` (${pos.tp_price:.8f})\n"
            f"🛑 Stop loss: `-{sl_pct}%` (${pos.sl_price:.8f})\n\n"
            f"[View on Solscan]({result['explorer']})\n\n"
            f"_Monitoring every 90s. I'll alert when TP or SL hits._"
        )

    # ── Handle Exit ──────────────────────────────────────────────────────────

    async def _handle_exit(self, pos_key: str, pos: Position, reason: str, current_price: float, pnl_pct: float):
        """Called by PositionMonitor when TP/SL is hit"""
        user_id = pos.user_id
        sym = pos.token_symbol

        # Get keypair
        key_bytes = get_private_key(user_id)
        if not key_bytes:
            await self.notify(user_id, f"⚠️ TP/SL triggered for *{sym}* but couldn't load wallet to exit!")
            close_position(pos_key, current_price, "", "error")
            return

        keypair = keypair_from_bytes(key_bytes)
        if not keypair:
            await self.notify(user_id, f"⚠️ TP/SL triggered for *{sym}* — invalid keypair, manual exit needed!")
            close_position(pos_key, current_price, "", "error")
            return

        reason_label = {
            "tp_hit": "🎯 TAKE PROFIT HIT",
            "sl_hit": "🛑 STOP LOSS HIT",
            "timeout": "⏰ 24H TIMEOUT",
        }.get(reason, "EXIT")

        await self.notify(user_id,
            f"{reason_label} — *{sym}*\n\n"
            f"PnL: `{pnl_pct:+.1f}%`\n"
            f"Selling `{pos.tokens_held:,} {sym}`..."
        )

        # Execute sell
        result = await sell_token(keypair, sym, pos.tokens_held)

        if result["success"]:
            sol_back = result["sol_received"]
            profit_sol = sol_back - pos.sol_spent
            close_position(pos_key, current_price, result["signature"], reason)

            emoji = "🟢" if pnl_pct > 0 else "🔴"
            await self.notify(user_id,
                f"{emoji} *Position Closed — {sym}*\n\n"
                f"Reason: {reason_label}\n"
                f"Entry: `${pos.entry_price_usd:.8f}` → Exit: `${current_price:.8f}`\n"
                f"PnL: `{pnl_pct:+.1f}%` ({profit_sol:+.4f} SOL)\n"
                f"SOL returned: `{sol_back:.4f} SOL`\n\n"
                f"[View on Solscan]({result['explorer']})"
            )
        else:
            await self.notify(user_id,
                f"⚠️ *Exit failed for {sym}*\n"
                f"Error: `{result.get('error')}`\n"
                f"PnL would be: `{pnl_pct:+.1f}%`\n"
                f"Please exit manually via your wallet!"
            )

    # ── Manual trade entry (user-triggered) ───────────────────────────────────

    async def manual_trade(self, user_id: int, symbol: str, signal: dict, price_data: Optional[dict]) -> str:
        """Triggered by /trade command — user manually fires a trade"""
        info = get_wallet_info(user_id)
        if not info:
            return "❌ No wallet connected. Use /connect first."

        settings = info["settings"]
        open_trades = get_user_positions(user_id, "open")
        max_trades = settings.get("max_open_trades", DEFAULT_MAX_TRADES)

        if len(open_trades) >= max_trades:
            return f"❌ Already at max {max_trades} open trades. Close one first."

        if any(p.token_symbol == symbol for p in open_trades):
            return f"⚠️ Already have an open position in {symbol}."

        should_trade, reason = evaluate_signal(signal, settings)
        if not should_trade:
            return f"⚠️ Signal doesn't meet your criteria:\n_{reason}_\n\nUse `/trade {symbol} force` to override."

        # Fire in background
        asyncio.create_task(self._execute_entry(user_id, signal, price_data, settings))
        return f"✅ Trade queued for *{symbol}* — executing now..."

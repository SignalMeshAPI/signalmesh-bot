"""
trading.py — Telegram command handlers for wallet connection and auto-trading

Commands:
  /connect       — Link Phantom wallet (sends instructions)
  /wallet        — Show connected wallet info + settings
  /autotrade on  — Enable auto-trading
  /autotrade off — Disable auto-trading
  /trade BONK    — Manually trigger a trade on a signal
  /positions     — Show open + recent closed positions
  /settings      — Update trading parameters
  /disconnect    — Wipe wallet data permanently
"""

import logging
import base58
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

logger = logging.getLogger(__name__)

# Conversation states
AWAITING_PRIVKEY = 1

# We'll inject these from bot.py at startup
_wallet_mod = None
_autotrader = None
_signal_fn = None
_price_fn = None
_safety_fn = None


def init(wallet_module, autotrader, signal_fn, price_fn, safety_fn):
    global _wallet_mod, _autotrader, _signal_fn, _price_fn, _safety_fn
    _wallet_mod = wallet_module
    _autotrader = autotrader
    _signal_fn = signal_fn
    _price_fn = price_fn
    _safety_fn = safety_fn


def _fmt_sol(n): return f"{n:.4f} SOL"
def _fmt_pct(n): return f"{n:+.1f}%" if n != 0 else "0.0%"


# ── /connect ──────────────────────────────────────────────────────────────────

async def connect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if _wallet_mod.is_connected(user_id):
        info = _wallet_mod.get_wallet_info(user_id)
        await update.message.reply_text(
            f"✅ Wallet already connected: `{info['pubkey'][:20]}...`\n\n"
            f"Use /disconnect to remove it, or /wallet to see details.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "🔐 *Connect Your Phantom Wallet*\n\n"
        "SignalMesh needs your *private key* to sign transactions on your behalf.\n\n"
        "⚠️ *Security notes:*\n"
        "• Your key is encrypted with AES-256 and never stored plaintext\n"
        "• It's only decrypted in-memory during trade execution\n"
        "• You can /disconnect and wipe it at any time\n"
        "• Use a *dedicated trading wallet* with only the SOL you want to risk\n"
        "• Never connect your main wallet\n\n"
        "📋 *How to export from Phantom:*\n"
        "Settings → Security & Privacy → Export Private Key\n\n"
        "Reply with your private key (base58 format) — this message will be deleted immediately.\n\n"
        "_Or type /cancel to abort._",
        parse_mode="Markdown"
    )
    return AWAITING_PRIVKEY


async def connect_receive_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    raw = update.message.text.strip()

    # Delete the message immediately for security
    try:
        await update.message.delete()
    except Exception:
        pass

    # Validate + load the private key
    try:
        from solders.keypair import Keypair
        
        # Try base58 decode
        key_bytes = base58.b58decode(raw)
        if len(key_bytes) not in (32, 64):
            raise ValueError(f"Invalid key length: {len(key_bytes)}")
        
        kp = Keypair.from_bytes(key_bytes) if len(key_bytes) == 64 else Keypair.from_seed(key_bytes)
        pubkey = str(kp.pubkey())

    except Exception as e:
        await update.message.reply_text(
            f"❌ Invalid private key format.\n\n"
            f"Make sure you're pasting the base58 private key from Phantom.\n"
            f"Error: `{str(e)[:80]}`\n\nTry /connect again.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    # Store encrypted
    success = _wallet_mod.store_wallet(user_id, key_bytes, pubkey)
    if not success:
        await update.message.reply_text("❌ Failed to store wallet. Please try again.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("✅ Enable AutoTrader now", callback_data="enable_autotrade")],
        [InlineKeyboardButton("⚙️ Configure settings first", callback_data="show_settings")],
    ]

    await update.message.reply_text(
        f"✅ *Wallet Connected!*\n\n"
        f"Address: `{pubkey}`\n\n"
        f"*Default settings:*\n"
        f"• Position size: `0.1 SOL` per trade\n"
        f"• Max open trades: `3`\n"
        f"• Take profit: `+50%`\n"
        f"• Stop loss: `-30%`\n"
        f"• Min safety score: `75/100`\n"
        f"• Min alpha score: `0.68`\n"
        f"• Min smart wallets in: `2`\n\n"
        f"AutoTrader is currently *OFF*. Enable it below or use `/autotrade on`.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ConversationHandler.END


async def connect_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled. Use /connect when you're ready.")
    return ConversationHandler.END


# ── /wallet ───────────────────────────────────────────────────────────────────

async def wallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _wallet_mod.is_connected(user_id):
        await update.message.reply_text(
            "❌ No wallet connected.\n\nUse /connect to link your Phantom wallet.",
            parse_mode="Markdown"
        )
        return

    info = _wallet_mod.get_wallet_info(user_id)
    s = info["settings"]
    enabled = s.get("enabled", False)
    
    from ..trader.positions import get_user_positions
    open_pos = get_user_positions(user_id, "open")
    closed_pos = get_user_positions(user_id, "tp_hit") + get_user_positions(user_id, "sl_hit")
    
    total_pnl = sum(p.pnl_pct for p in closed_pos)
    wins = sum(1 for p in closed_pos if p.pnl_pct > 0)

    status_icon = "🟢 ACTIVE" if enabled else "⚫ PAUSED"

    keyboard = [
        [InlineKeyboardButton("🟢 Enable" if not enabled else "⏸ Pause", callback_data="toggle_autotrade"),
         InlineKeyboardButton("⚙️ Settings", callback_data="show_settings")],
        [InlineKeyboardButton("📊 Positions", callback_data="show_positions"),
         InlineKeyboardButton("🗑 Disconnect", callback_data="confirm_disconnect")],
    ]

    await update.message.reply_text(
        f"💼 *Your SignalMesh Wallet*\n\n"
        f"Address: `{info['pubkey'][:20]}...`\n"
        f"Status: {status_icon}\n\n"
        f"*Trading Settings:*\n"
        f"• Position size: `{s.get('max_position_sol', 0.1)} SOL`\n"
        f"• Max trades: `{s.get('max_open_trades', 3)}`\n"
        f"• Take profit: `+{s.get('tp_pct', 50)}%`\n"
        f"• Stop loss: `-{s.get('sl_pct', 30)}%`\n"
        f"• Min safety: `{s.get('min_safety_score', 75)}/100`\n"
        f"• Min alpha: `{s.get('min_alpha_score', 0.68)}`\n\n"
        f"*Performance:*\n"
        f"• Open trades: `{len(open_pos)}`\n"
        f"• Closed trades: `{len(closed_pos)}` ({wins} wins)\n"
        f"• Avg PnL: `{total_pnl/max(len(closed_pos),1):+.1f}%`",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ── /autotrade ────────────────────────────────────────────────────────────────

async def autotrade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _wallet_mod.is_connected(user_id):
        await update.message.reply_text("❌ Connect a wallet first: /connect")
        return

    arg = (context.args[0].lower() if context.args else "").strip()

    if arg == "on":
        _wallet_mod.update_settings(user_id, enabled=True)
        info = _wallet_mod.get_wallet_info(user_id)
        s = info["settings"]
        await update.message.reply_text(
            f"🟢 *AutoTrader ENABLED*\n\n"
            f"I'm now scanning signals every 3 minutes.\n"
            f"I'll trade when:\n"
            f"• Safety score ≥ `{s['min_safety_score']}/100`\n"
            f"• Alpha score ≥ `{s['min_alpha_score']}`\n"
            f"• Smart wallets in ≥ `{s['min_wallets_in']}`\n"
            f"• Max `{s['max_position_sol']} SOL` per trade\n"
            f"• TP `+{s['tp_pct']}%` | SL `-{s['sl_pct']}%`\n\n"
            f"_I'll message you when I enter or exit a position._\n"
            f"Use `/autotrade off` to pause at any time.",
            parse_mode="Markdown"
        )
    elif arg == "off":
        _wallet_mod.update_settings(user_id, enabled=False)
        await update.message.reply_text(
            "⏸ *AutoTrader PAUSED*\n\n"
            "I won't open new trades. Existing positions still monitored for TP/SL.\n"
            "Use `/autotrade on` to resume.",
            parse_mode="Markdown"
        )
    else:
        info = _wallet_mod.get_wallet_info(user_id)
        enabled = info["settings"].get("enabled", False)
        await update.message.reply_text(
            f"AutoTrader is currently {'🟢 *ON*' if enabled else '⏸ *OFF*'}.\n\n"
            f"Usage:\n`/autotrade on` — start trading\n`/autotrade off` — pause",
            parse_mode="Markdown"
        )


# ── /trade (manual) ───────────────────────────────────────────────────────────

async def trade_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _wallet_mod.is_connected(user_id):
        await update.message.reply_text("❌ Connect a wallet first: /connect")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/trade BONK` — manually trigger a trade\n"
            "I'll run the signal check first, then execute if it passes your criteria.\n\n"
            "_Tip: Add `force` to bypass signal check: `/trade BONK force`_",
            parse_mode="Markdown"
        )
        return

    symbol = context.args[0].upper()
    force = len(context.args) > 1 and context.args[1].lower() == "force"

    msg = await update.message.reply_text(f"🔍 Running signal for *{symbol}*...", parse_mode="Markdown")

    price_data = await _price_fn(symbol)
    safety = _safety_fn(symbol, price_data)
    signal = _signal_fn(symbol, price_data, safety)

    if not force:
        result_msg = await _autotrader.manual_trade(user_id, symbol, signal, price_data)
        await msg.edit_text(result_msg, parse_mode="Markdown")
    else:
        # Force trade — bypass signal check
        info = _wallet_mod.get_wallet_info(user_id)
        if info:
            settings = info["settings"]
            import asyncio
            asyncio.create_task(_autotrader._execute_entry(user_id, signal, price_data, settings))
            await msg.edit_text(
                f"⚡ *Force trade queued for {symbol}*\n\n"
                f"Safety: `{signal['safety_score']}/100` | Alpha: `{signal['alpha_score']}`\n"
                f"Executing regardless of criteria...",
                parse_mode="Markdown"
            )


# ── /positions ────────────────────────────────────────────────────────────────

async def positions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _wallet_mod.is_connected(user_id):
        await update.message.reply_text("❌ No wallet connected. Use /connect.")
        return

    from ..trader.positions import get_user_positions, get_current_price
    open_pos = get_user_positions(user_id, "open")

    if not open_pos:
        # Show recent closed
        tp = get_user_positions(user_id, "tp_hit")
        sl = get_user_positions(user_id, "sl_hit")
        closed = sorted(tp + sl, key=lambda p: p.entry_ts, reverse=True)[:5]

        if not closed:
            await update.message.reply_text(
                "📊 *No positions yet.*\n\n"
                "Use `/autotrade on` to start auto-trading,\nor `/trade BONK` to manually enter a position.",
                parse_mode="Markdown"
            )
            return

        text = "📋 *Recent Closed Positions:*\n\n"
        for p in closed:
            icon = "🟢" if p.pnl_pct > 0 else "🔴"
            text += (
                f"{icon} *{p.token_symbol}* — {p.pnl_pct:+.1f}%\n"
                f"   Entry `${p.entry_price_usd:.8f}` → Exit `${p.exit_price_usd:.8f}`\n"
                f"   Spent `{p.sol_spent} SOL` | Status: `{p.status}`\n\n"
            )
        await update.message.reply_text(text, parse_mode="Markdown")
        return

    # Show open positions with live prices
    msg = await update.message.reply_text("⏳ Fetching live prices...", parse_mode="Markdown")
    text = f"📊 *Open Positions ({len(open_pos)})*\n\n"

    for p in open_pos:
        current = await get_current_price(p.token_symbol)
        if current:
            pnl = p.current_pnl_pct(current)
            icon = "🟢" if pnl > 0 else "🔴"
            text += (
                f"{icon} *{p.token_symbol}* — {pnl:+.1f}%\n"
                f"   Entry: `${p.entry_price_usd:.8f}`\n"
                f"   Current: `${current:.8f}`\n"
                f"   TP: `${p.tp_price:.8f}` (+{p.tp_pct}%)\n"
                f"   SL: `${p.sl_price:.8f}` (-{p.sl_pct}%)\n"
                f"   Age: `{p.age_minutes}min` | SOL in: `{p.sol_spent}`\n\n"
            )
        else:
            text += (
                f"⬛ *{p.token_symbol}* — price unavailable\n"
                f"   Entry: `${p.entry_price_usd:.8f}` | SOL: `{p.sol_spent}`\n\n"
            )

    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="refresh_positions")]]
    await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


# ── /settings ─────────────────────────────────────────────────────────────────

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _wallet_mod.is_connected(user_id):
        await update.message.reply_text("❌ Connect a wallet first: /connect")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚙️ *AutoTrader Settings*\n\n"
            "Usage: `/settings <param> <value>`\n\n"
            "*Parameters:*\n"
            "`/settings sol 0.15` — SOL per trade (e.g. 0.05–1.0)\n"
            "`/settings tp 75` — Take profit % (e.g. 50, 75, 100)\n"
            "`/settings sl 25` — Stop loss % (e.g. 20, 30)\n"
            "`/settings safety 80` — Min safety score (e.g. 70–95)\n"
            "`/settings alpha 0.70` — Min alpha score (e.g. 0.60–0.80)\n"
            "`/settings wallets 3` — Min smart wallets (e.g. 1–5)\n"
            "`/settings maxtrades 2` — Max open trades at once\n\n"
            "_Changes take effect immediately._",
            parse_mode="Markdown"
        )
        return

    param = context.args[0].lower()
    try:
        val = float(context.args[1])
    except ValueError:
        await update.message.reply_text(f"❌ Invalid value: `{context.args[1]}`", parse_mode="Markdown")
        return

    mapping = {
        "sol": ("max_position_sol", 0.01, 5.0, "SOL per trade"),
        "tp": ("tp_pct", 10, 500, "Take profit %"),
        "sl": ("sl_pct", 5, 80, "Stop loss %"),
        "safety": ("min_safety_score", 50, 100, "Min safety score"),
        "alpha": ("min_alpha_score", 0.40, 0.95, "Min alpha score"),
        "wallets": ("min_wallets_in", 0, 10, "Min smart wallets"),
        "maxtrades": ("max_open_trades", 1, 10, "Max open trades"),
    }

    if param not in mapping:
        await update.message.reply_text(f"❌ Unknown parameter: `{param}`", parse_mode="Markdown")
        return

    key, min_v, max_v, label = mapping[param]
    if not (min_v <= val <= max_v):
        await update.message.reply_text(
            f"❌ `{label}` must be between `{min_v}` and `{max_v}`",
            parse_mode="Markdown"
        )
        return

    _wallet_mod.update_settings(user_id, **{key: val})
    await update.message.reply_text(
        f"✅ Updated: *{label}* → `{val}`",
        parse_mode="Markdown"
    )


# ── /disconnect ───────────────────────────────────────────────────────────────

async def disconnect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not _wallet_mod.is_connected(user_id):
        await update.message.reply_text("No wallet connected.")
        return

    # Confirm step
    keyboard = [
        [InlineKeyboardButton("🗑 Yes, wipe my wallet data", callback_data="confirm_disconnect_yes")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_disconnect")],
    ]
    await update.message.reply_text(
        "⚠️ *Are you sure?*\n\n"
        "This will permanently delete your encrypted private key from SignalMesh.\n"
        "Open positions will still be in your wallet — you'll need to close them manually.\n\n"
        "_This cannot be undone._",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

"""
positions.py — Position tracker and auto-exit monitor

Tracks open trades, monitors prices for TP/SL hits,
fires exit orders automatically.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)

COINCAP_BASE = "https://api.coincap.io/v2"

SYMBOL_TO_COINCAP = {
    "BONK":"bonk","WIF":"dogwifcoin","SOL":"solana","ETH":"ethereum",
    "POPCAT":"popcat","MEW":"cat-in-a-dogs-world","BOME":"book-of-meme",
    "SAMO":"samoyedcoin","FARTCOIN":"fartcoin","JUP":"jupiter-ag",
}


@dataclass
class Position:
    user_id: int
    token_symbol: str
    chain: str
    entry_price_usd: float
    sol_spent: float
    tokens_held: int          # raw token units
    tp_pct: float             # e.g. 50 = +50%
    sl_pct: float             # e.g. 30 = -30% (stored positive)
    entry_ts: float = field(default_factory=time.time)
    tx_hash: str = ""
    status: str = "open"      # open | tp_hit | sl_hit | manual_closed | error
    exit_price_usd: float = 0.0
    exit_tx_hash: str = ""
    pnl_pct: float = 0.0

    @property
    def tp_price(self) -> float:
        return self.entry_price_usd * (1 + self.tp_pct / 100)

    @property
    def sl_price(self) -> float:
        return self.entry_price_usd * (1 - self.sl_pct / 100)

    @property
    def age_minutes(self) -> int:
        return int((time.time() - self.entry_ts) / 60)

    def current_pnl_pct(self, current_price: float) -> float:
        if self.entry_price_usd <= 0:
            return 0.0
        return ((current_price - self.entry_price_usd) / self.entry_price_usd) * 100


# ── In-memory position store ──────────────────────────────────────────────────
# Production: use Redis or PostgreSQL
_positions: dict[str, Position] = {}  # key = f"{user_id}_{token}"


def add_position(pos: Position) -> str:
    key = f"{pos.user_id}_{pos.token_symbol}_{int(pos.entry_ts)}"
    _positions[key] = pos
    return key


def get_user_positions(user_id: int, status: str = "open") -> list[Position]:
    return [p for p in _positions.values() if p.user_id == user_id and p.status == status]


def get_all_open() -> list[tuple[str, Position]]:
    return [(k, p) for k, p in _positions.items() if p.status == "open"]


def close_position(key: str, exit_price: float, exit_tx: str, status: str):
    if key in _positions:
        p = _positions[key]
        p.status = status
        p.exit_price_usd = exit_price
        p.exit_tx_hash = exit_tx
        p.pnl_pct = p.current_pnl_pct(exit_price)


# ── Price fetcher ─────────────────────────────────────────────────────────────

async def get_current_price(symbol: str) -> Optional[float]:
    coin_id = SYMBOL_TO_COINCAP.get(symbol.upper())
    if not coin_id:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{COINCAP_BASE}/assets/{coin_id}",
                timeout=aiohttp.ClientTimeout(total=6)
            ) as r:
                if r.status == 200:
                    data = (await r.json())["data"]
                    return float(data["priceUsd"] or 0)
    except Exception:
        pass
    return None


# ── Monitor loop ──────────────────────────────────────────────────────────────

class PositionMonitor:
    """
    Background task that monitors all open positions and triggers exits.
    The bot calls monitor.start() on startup and passes a callback
    for when a position needs to be closed.
    """

    def __init__(self, on_exit_needed):
        self.on_exit_needed = on_exit_needed  # async callback(key, position, reason, current_price)
        self._running = False
        self._task = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._loop())
            logger.info("Position monitor started")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self):
        while self._running:
            try:
                open_positions = get_all_open()
                if open_positions:
                    # Batch price fetches with small delay between
                    seen_symbols = set()
                    price_cache: dict[str, float] = {}

                    for key, pos in open_positions:
                        if pos.token_symbol not in seen_symbols:
                            price = await get_current_price(pos.token_symbol)
                            if price:
                                price_cache[pos.token_symbol] = price
                            seen_symbols.add(pos.token_symbol)
                            await asyncio.sleep(0.3)

                    # Check each position
                    for key, pos in open_positions:
                        price = price_cache.get(pos.token_symbol)
                        if not price:
                            continue

                        pnl = pos.current_pnl_pct(price)

                        if price >= pos.tp_price:
                            logger.info(f"TP hit: {pos.token_symbol} user={pos.user_id} pnl=+{pnl:.1f}%")
                            await self.on_exit_needed(key, pos, "tp_hit", price, pnl)

                        elif price <= pos.sl_price:
                            logger.info(f"SL hit: {pos.token_symbol} user={pos.user_id} pnl={pnl:.1f}%")
                            await self.on_exit_needed(key, pos, "sl_hit", price, pnl)

                        # Hard stop: close after 24h regardless
                        elif pos.age_minutes >= 1440:
                            logger.info(f"24h timeout: {pos.token_symbol} user={pos.user_id}")
                            await self.on_exit_needed(key, pos, "timeout", price, pnl)

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

            # Check every 90 seconds
            await asyncio.sleep(90)

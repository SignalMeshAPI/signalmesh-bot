"""
/start, /subscribe, /chains handlers
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode


WELCOME_MSG = """
🔗 *Welcome to SignalMesh*

The intelligence layer for crypto AI agents.
Real-time signals, safety checks, and whale tracking — across every chain.

━━━━━━━━━━━━━━━━━━━━
*Commands:*

📡 `/signal [token]` — Sentiment signal
`/signal BONK`
`/signal WIF solana`

🛡 `/safety [address]` — Safety check
`/safety 0xABC123...`

🐋 `/whales [chain]` — Smart money activity
`/whales solana`
`/whales sui`

🚀 `/launch` — Latest new token launches

💰 `/price [token]` — Quick price check

⛓ `/chains` — Supported chains

💎 `/subscribe` — Get full API access
━━━━━━━━━━━━━━━━━━━━

Powered by *SignalMesh API*
signalmesh.dev
"""


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🔑 Get API Access", url="https://signalmesh.dev"),
            InlineKeyboardButton("📖 Docs", url="https://docs.signalmesh.dev"),
        ],
        [
            InlineKeyboardButton("🐦 Follow @SignalMeshAPI", url="https://x.com/SignalMeshAPI"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        WELCOME_MSG,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup,
    )


async def handle_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
💎 *SignalMesh API Pricing*

┌─────────────────────────────
│ 🆓 *Builder* — Free
│ 10K calls/mo · All chains (1hr delay)
│ REST only · No execution
│
│ 🤖 *Agent* — $49/mo
│ 500K calls/mo · Real-time
│ All 9 modules · WebSocket · MCP
│ /agent/context endpoint
│
│ ⚡ *Scalper* — $99/mo ← Most Popular
│ Agent + Trade Execution
│ GMGN safety filters
│ 500 trades/mo · OpenClaw template
│
│ 🏦 *Pro* — $199/mo
│ Unlimited everything
│ DeFi + RWA modules
│ 2yr history · SLA
└─────────────────────────────

Get started → signalmesh.dev
"""
    keyboard = [[InlineKeyboardButton("🚀 Start Free", url="https://signalmesh.dev")]]
    await update.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_chains(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """
⛓ *Supported Chains*

*Tier 1 — Live Now*
• Solana `(SOL)` — ~3s detection
• SUI `(SUI)` — ~5s detection
• TON `(TON)` — ~8s detection

*Tier 2 — Coming Month 2*
• Ethereum `(ETH)`
• Base `(BASE)`
• BNB Chain `(BSC)`

*Tier 3 — Coming Month 5*
• Tron `(TRX)`
• Arbitrum `(ARB)`

Pass chain name to any command:
`/signal DOGS ton`
`/whales sui`
`/launch base`
"""
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

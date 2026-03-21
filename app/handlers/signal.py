"""
/signal [token] [chain?] handler

Usage:
  /signal BONK
  /signal WIF solana
  /signal DOGS ton

Phase 1: Returns mock data (realistic demo output)
Phase 2: Connects to live SignalMesh /signal/sentiment endpoint
"""

import random
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from app.utils.api import call_signalmesh_api
from app.utils.formatting import chain_emoji, sentiment_bar, confidence_stars


HELP_MSG = "Usage: `/signal [token]` or `/signal [token] [chain]`\nExample: `/signal BONK` or `/signal WIF solana`"


async def handle_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    if not args:
        await update.message.reply_text(HELP_MSG, parse_mode=ParseMode.MARKDOWN)
        return

    token = args[0].upper()
    chain = args[1].lower() if len(args) > 1 else "solana"

    # Show typing indicator
    await update.message.chat.send_action("typing")

    # Try live API first, fall back to demo data
    data = await call_signalmesh_api(f"/v1/signal/sentiment?token={token}&chain={chain}")
    if not data:
        data = _mock_signal(token, chain)

    score = data.get("sentiment_score", 0.0)
    velocity = data.get("velocity", "stable")
    narrative = data.get("narrative_tag", "none")
    sources = data.get("sources", {})
    trade_now = data.get("trade_now", False)
    confidence = data.get("confidence", 0.0)
    summary = data.get("agent_summary", "No summary available.")

    # Build signal indicator
    if score >= 0.7:
        signal_icon = "🟢"
        signal_label = "BULLISH"
    elif score >= 0.4:
        signal_icon = "🟡"
        signal_label = "NEUTRAL"
    else:
        signal_icon = "🔴"
        signal_label = "BEARISH"

    trade_badge = "✅ *TRADE SIGNAL*" if trade_now else "⏸ *WAIT*"

    msg = f"""
{chain_emoji(chain)} *{token}* — Signal Report

{signal_icon} *Sentiment:* {signal_label} `{score:.2f}`
{sentiment_bar(score)}

📊 *Velocity:* {velocity}
🏷 *Narrative:* `{narrative}`
{confidence_stars(confidence)} *Confidence:* `{confidence:.0%}`

*Sources:*
• X/Twitter: `{sources.get('x_score', 'N/A')}`
• Reddit: `{sources.get('reddit_score', 'N/A')}`
• Telegram: `{sources.get('telegram_score', 'N/A')}`

━━━━━━━━━━━━━━━
{trade_badge}

💬 _{summary}_

━━━━━━━━━━━━━━━
🔑 Full intelligence → /subscribe
🛡 Safety check → `/safety {token}`
"""

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


def _mock_signal(token: str, chain: str) -> dict:
    """Realistic mock data for demo — replace with live API in Phase 2"""
    score = round(random.uniform(0.45, 0.92), 2)
    confidence = round(random.uniform(0.60, 0.88), 2)
    narratives = ["celebrity_meme", "ai_narrative", "political_event", "community_driven", "ecosystem_token"]
    velocities = ["accelerating 🚀", "stable →", "slowing ↘"]

    return {
        "token": token,
        "chain": chain,
        "sentiment_score": score,
        "velocity": random.choice(velocities),
        "narrative_tag": random.choice(narratives),
        "sources": {
            "x_score": round(random.uniform(0.5, 0.95), 2),
            "reddit_score": round(random.uniform(0.4, 0.9), 2),
            "telegram_score": round(random.uniform(0.5, 0.95), 2),
        },
        "trade_now": score > 0.70 and confidence > 0.72,
        "confidence": confidence,
        "agent_summary": (
            f"{token} showing {'strong bullish' if score > 0.7 else 'mixed'} signals. "
            f"Sentiment {score:.2f}/1.0 with {confidence:.0%} confidence across X, Reddit and Telegram. "
            f"{'Smart money entering. Consider position.' if score > 0.75 else 'Wait for clearer confirmation.'}"
        ),
    }

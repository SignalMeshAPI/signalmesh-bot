"""
/whales, /launch, /price handlers
"""

import random
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from app.utils.api import call_signalmesh_api
from app.utils.formatting import chain_emoji


# ─── /whales ───────────────────────────────────────────────────────────────

async def handle_whales(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chain = context.args[0].lower() if context.args else "solana"

    await update.message.chat.send_action("typing")

    data = await call_signalmesh_api(f"/v1/wallet/whales?chain={chain}&limit=5")
    wallets = data.get("wallets", _mock_whales(chain)) if data else _mock_whales(chain)

    lines = [f"{chain_emoji(chain)} *Smart Money Activity — {chain.upper()}*\n"]

    for i, w in enumerate(wallets[:5], 1):
        action_icon = "🟢" if w["action"] == "buying" else "🔴"
        lines.append(
            f"{action_icon} *#{i}* `{w['address']}`\n"
            f"   Type: `{w['archetype']}` · Win rate: `{w['win_rate']}%`\n"
            f"   {w['action'].upper()} → *{w['token']}* `${w['value_usd']:,}`\n"
            f"   _{w['time_ago']}_\n"
        )

    lines.append("━━━━━━━━━━━━━━━")
    lines.append("🔑 Copy-trade scores + full history → /subscribe")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


def _mock_whales(chain: str) -> list:
    tokens = {
        "solana": ["BONK", "WIF", "POPCAT", "MEW", "BOME"],
        "sui": ["HIPPO", "BLUB", "FUD", "LOFI", "BEEG"],
        "ton": ["DOGS", "NOT", "FISH", "CATS", "GLDR"],
        "ethereum": ["PEPE", "SHIB", "FLOKI", "MEME", "MOG"],
    }.get(chain, ["TOKEN1", "TOKEN2", "TOKEN3"])

    archetypes = ["smart_money", "whale", "degen", "smart_money", "whale"]
    actions = ["buying", "buying", "selling", "buying", "selling"]
    times = ["2m ago", "8m ago", "14m ago", "21m ago", "35m ago"]
    addresses = [
        "9xK3...mR7z", "BnPq...4fWx", "CvYt...8kLm",
        "DwZs...2nQp", "EuXr...6jHv"
    ]

    return [
        {
            "address": addresses[i],
            "archetype": archetypes[i],
            "win_rate": random.randint(62, 89),
            "action": actions[i],
            "token": random.choice(tokens),
            "value_usd": random.randint(5000, 180000),
            "time_ago": times[i],
        }
        for i in range(5)
    ]


# ─── /launch ───────────────────────────────────────────────────────────────

async def handle_launch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chain = context.args[0].lower() if context.args else "solana"

    await update.message.chat.send_action("typing")

    data = await call_signalmesh_api(f"/v1/launch/score?chain={chain}&limit=5")
    launches = data.get("launches", _mock_launches(chain)) if data else _mock_launches(chain)

    lines = [f"{chain_emoji(chain)} *New Token Launches — {chain.upper()}*\n"]

    for launch in launches:
        score = launch["safety_score"]
        icon = "🟢" if score >= 75 else "🟡" if score >= 50 else "🔴"
        lines.append(
            f"{icon} *{launch['name']}* `({launch['symbol']})`\n"
            f"   Safety: `{score}/100` · LP: `{launch['lp_usd']:,} USDC`\n"
            f"   Narrative: `{launch['narrative']}` · _{launch['age']}_\n"
        )

    lines.append("━━━━━━━━━━━━━━━")
    lines.append("🛡 Check any token → `/safety [address]`")
    lines.append("🔑 Stream live launches (WSS) → /subscribe")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


def _mock_launches(chain: str) -> list:
    names = ["MoonPup", "GigaFi", "SolBull", "ChadCoin", "PepeX"]
    symbols = ["MPUP", "GIFI", "SBUL", "CHAD", "PEPX"]
    narratives = ["community_meme", "ai_narrative", "celebrity_meme", "fair_launch", "ecosystem"]

    return [
        {
            "name": names[i],
            "symbol": symbols[i],
            "safety_score": random.randint(42, 91),
            "lp_usd": random.randint(8000, 95000),
            "narrative": narratives[i],
            "age": f"{random.randint(2, 58)}m ago",
        }
        for i in range(5)
    ]


# ─── /price ────────────────────────────────────────────────────────────────

async def handle_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Usage: `/price [token]`\nExample: `/price BONK`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    token = context.args[0].upper()
    chain = context.args[1].lower() if len(context.args) > 1 else "solana"

    await update.message.chat.send_action("typing")

    # Mock price data — replace with CoinGecko/Jupiter price API
    price = round(random.uniform(0.000001, 0.0085), 8)
    change_24h = round(random.uniform(-18, 42), 2)
    volume_24h = random.randint(500_000, 25_000_000)
    mcap = random.randint(1_000_000, 180_000_000)

    change_icon = "📈" if change_24h > 0 else "📉"
    change_sign = "+" if change_24h > 0 else ""

    msg = f"""
{chain_emoji(chain)} *{token}* Price

💲 *${price:,.8f}*
{change_icon} 24h: `{change_sign}{change_24h}%`

📊 Volume 24h: `${volume_24h:,}`
🏦 Market Cap: `${mcap:,}`

━━━━━━━━━━━━━━━
📡 Get signal → `/signal {token}`
🛡 Safety check → `/safety {token}`
"""

    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

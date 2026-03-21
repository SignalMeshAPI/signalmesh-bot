"""
Formatting helpers for SignalMesh bot messages
"""


def chain_emoji(chain: str) -> str:
    return {
        "solana": "◎",
        "sol":    "◎",
        "sui":    "🔷",
        "ton":    "💎",
        "ethereum": "⟠",
        "eth":    "⟠",
        "base":   "🔵",
        "bsc":    "🟡",
        "bnb":    "🟡",
        "tron":   "🔴",
        "trx":    "🔴",
    }.get(chain.lower(), "⛓")


def sentiment_bar(score: float, width: int = 12) -> str:
    """Returns a visual bar like: ████████░░░░ 0.81"""
    filled = round(score * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"`{bar}`"


def confidence_stars(confidence: float) -> str:
    stars = round(confidence * 5)
    return "⭐" * stars + "☆" * (5 - stars)


def score_color(score: int) -> str:
    if score >= 75:
        return "🟢"
    elif score >= 50:
        return "🟡"
    else:
        return "🔴"


def format_address(address: str, chars: int = 6) -> str:
    """Shorten a wallet address: 0x1234...5678"""
    if len(address) <= chars * 2 + 3:
        return address
    return f"{address[:chars]}...{address[-chars:]}"


def format_usd(value: float) -> str:
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:.2f}"

# @SignalMeshBot

Telegram demo bot for [SignalMesh API](https://signalmesh.dev) — the intelligence layer for crypto AI agents.

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + quick actions |
| `/signal BONK` | Full agent signal (safety + sentiment + smart money) |
| `/signal WIF solana` | Signal for specific chain |
| `/price SOL` | Real-time price from CoinCap |
| `/safety <token>` | 9-point enhanced safety check |
| `/whales solana` | Top smart money wallets + recent moves |
| `/launch` | New token launches in last hour |
| `/alpha` | Top 3 opportunities right now |
| `/chains` | Supported chains overview |
| `/subscribe` | Pricing tiers |

## Live Data Sources

- **Prices**: [CoinCap API](https://coincap.io) — completely free, no key required
- **Safety scoring**: Enhanced 9-point check (vs GMGN's 6)
- **Signals**: SignalMesh alpha scoring engine

## Deploy

```bash
pip install -r requirements.txt
BOT_TOKEN=your_token python bot.py
```

Or runs 24/7 free on GitHub Actions via `.github/workflows/bot.yml`.

## Part of SignalMesh API

signalmesh.dev — One API key. Nine intelligence modules. Built for crypto agents.

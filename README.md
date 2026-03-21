# @SignalMeshBot

The official Telegram bot for [SignalMesh API](https://signalmesh.dev) — the intelligence layer for crypto AI agents.

## Commands

| Command | Description |
|---------|-------------|
| `/signal BONK` | Real-time sentiment signal for any token |
| `/signal WIF solana` | Signal with chain specified |
| `/safety 0xABC...` | 6-point GMGN-style safety check |
| `/whales solana` | Smart money wallet activity |
| `/launch` | Latest new token launches with safety scores |
| `/price BONK` | Quick price check |
| `/chains` | Supported chains |
| `/subscribe` | Upgrade to full API access |

## Setup

```bash
# 1. Clone and install
git clone https://github.com/signalmesh/signalmesh-bot
cd signalmesh-bot
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env and add your BOT_TOKEN from BotFather

# 3. Run
python bot.py
```

## Architecture

```
bot.py                    ← Entry point, registers handlers
app/
  handlers/
    start.py              ← /start, /subscribe, /chains
    signal.py             ← /signal [token] [chain]
    safety.py             ← /safety [token_or_address]
    whales.py             ← /whales [chain]
    launch.py             ← /launch [chain]
    price.py              ← /price [token]
  utils/
    api.py                ← SignalMesh API client (live or mock)
    formatting.py         ← Message formatting helpers
```

## Phase 1 vs Phase 2

**Phase 1 (Now):** Bot runs with realistic mock data — demonstrates the full UX without a live API.

**Phase 2 (Week 5):** Set `SIGNALMESH_API_KEY` in `.env` and the bot automatically connects to the live SignalMesh API. Zero code changes needed.

## Deployment (Railway — $5/mo)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Deploy
railway login
railway init
railway up
railway variables set BOT_TOKEN=your_token_here
```

## Links

- Website: [signalmesh.dev](https://signalmesh.dev)
- API Docs: [docs.signalmesh.dev](https://docs.signalmesh.dev)
- X: [@SignalMeshAPI](https://x.com/SignalMeshAPI)

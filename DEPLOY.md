# @SignalMeshBot — Free Deployment Guide

Three options, all completely free. Pick the one that fits you right now.

---

## Option 1: Run locally (right now, zero cost)

Best for: Beta testing while you're still building.
The bot only needs to be running when you're active — for demos, testing, beta users.

```bash
cd signalmesh-bot
cp .env.example .env
# Add your BOT_TOKEN to .env

pip install -r requirements.txt
python bot.py
```

Bot is live as long as your terminal is open. That's it.
**Cost: $0. No accounts needed.**

---

## Option 2: Oracle Cloud Always Free (permanent, 24/7)

Best for: When you want the bot live 24/7 without ever paying.

Oracle gives you a free ARM server with **4 CPU cores and 24GB RAM — free forever**.
That's more compute than a $40/mo server anywhere else. No credit card required to stay free.

### Step 1 — Sign up
Go to: https://www.oracle.com/cloud/free/
Click "Start for free" — create account (requires a credit card for identity verification, but you will NOT be charged as long as you only use Always Free resources)

### Step 2 — Create your free VM
1. In Oracle Cloud console → Compute → Instances → Create Instance
2. Shape: **Ampere A1** (ARM) — select "Always Free eligible"
3. 1 OCPU, 6GB RAM (well within the free limit)
4. OS: Ubuntu 22.04
5. Add your SSH key (generate one if needed: `ssh-keygen -t ed25519`)
6. Click Create

### Step 3 — Connect and deploy
```bash
# SSH into your free server
ssh ubuntu@YOUR_SERVER_IP

# Install Python
sudo apt update && sudo apt install python3-pip python3-venv -y

# Clone your bot (once it's on GitHub)
git clone https://github.com/signalmesh/signalmesh-bot
cd signalmesh-bot

# Set up environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
echo "BOT_TOKEN=your_token_here" > .env

# Run it forever (survives terminal close + server restarts)
pip install pm2 || npm install -g pm2
pm2 start "python bot.py" --name signalmesh-bot
pm2 startup   # run the command it gives you
pm2 save
```

**Cost: $0 forever. No expiry. No usage limits.**

---

## Option 3: Google Cloud Free Tier (also free forever)

Google gives you one free e2-micro VM in US regions forever.
Less RAM than Oracle (1GB vs 24GB) but works fine for a Telegram bot.

```bash
# After creating your free VM at cloud.google.com
# Same deployment steps as Oracle Option 2 above
```

**Cost: $0 forever in us-central1, us-east1, or us-west1**

---

## Recommendation

| Right now | Phase 1 (beta) | When you're ready for 24/7 |
|-----------|----------------|---------------------------|
| Run locally | Run locally | Oracle Cloud Always Free |

Don't set up any hosting until you need 24/7 uptime.
The bot running on your laptop is perfect for the first 2-4 weeks.
When you need it live permanently → Oracle, no payment ever needed.

---

## When you DO make money → upgrade

Your first $99/mo from a Scalper tier customer pays for:
- Railway ($5/mo) — for a proper managed deployment
- signalmesh.dev domain ($13/yr)
- With $81 left over


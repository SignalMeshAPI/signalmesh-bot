# GitHub Setup — @SignalMeshBot Running Free 24/7

## How it works

GitHub Actions gives you **unlimited free compute minutes on public repos**.
The workflow runs the bot for 50 minutes, then a fresh job automatically
takes over — zero gaps, zero cost, forever.

```
Every 50 mins:  [Job starts] → bot runs → [Next job starts] → bot runs → ...
                                    ↑ overlap ensures no downtime
```

---

## Step 1 — Create the GitHub Org (one time)

1. Go to: https://github.com/organizations/new
2. Plan: **Free**
3. Organization name: `signalmesh`
4. Contact email: your email
5. Click **Create organization**

You now have: `github.com/signalmesh`

---

## Step 2 — Create the repo

1. Go to: https://github.com/organizations/signalmesh/repositories/new
2. Repository name: `signalmesh-bot`
3. Visibility: **Public** ← IMPORTANT (public = unlimited free Actions minutes)
4. Click **Create repository**

---

## Step 3 — Push the bot code

In your terminal, from the `signalmesh-bot` folder:

```bash
git init
git add .
git commit -m "Initial commit — @SignalMeshBot"
git branch -M main
git remote add origin https://github.com/signalmesh/signalmesh-bot.git
git push -u origin main
```

---

## Step 4 — Add your Bot Token as a Secret (CRITICAL)

This keeps your token out of the code but makes it available to Actions.

1. Go to your repo: https://github.com/signalmesh/signalmesh-bot
2. Click **Settings** tab
3. Left sidebar → **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Name: `BOT_TOKEN`
6. Value: paste your BotFather token
7. Click **Add secret**

Optional (add when API is live):
- `SIGNALMESH_API_KEY` → your SignalMesh API key
- `SIGNALMESH_API_URL` → https://api.signalmesh.dev

---

## Step 5 — Start the bot

The workflow runs automatically on schedule. To start it immediately:

1. Go to: https://github.com/signalmesh/signalmesh-bot/actions
2. Click **SignalMesh Bot — 24/7** in the left panel
3. Click **Run workflow** → **Run workflow**

Your bot is now live. Open Telegram and message @SignalMeshBot — it should respond.

---

## Monitoring

Check if the bot is running:
- https://github.com/signalmesh/signalmesh-bot/actions
- Green checkmarks = running ✅
- Red X = something went wrong, click to see logs

The workflow auto-runs every 50 minutes forever.
You never need to touch it again.

---

## Troubleshooting

**Bot not responding?**
1. Check Actions tab — is there a recent successful run?
2. Click the run → click the job → check the logs
3. Most common issue: BOT_TOKEN secret not set correctly

**"BOT_TOKEN not set" error in logs?**
- Go to Settings → Secrets → make sure BOT_TOKEN exists exactly as typed

**Want to update the bot code?**
```bash
# Make your changes, then:
git add .
git commit -m "Update bot"
git push
```
The next scheduled run automatically uses the new code.

---

## Cost: $0.00 forever

Public repos on GitHub get unlimited Actions minutes.
No credit card. No expiry. No usage limits for what we're doing here.

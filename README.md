# A Clinic Bot

Discord bot that turns raw notes into structured rows in Google Sheets and tasks in Notion, using Claude to do the structuring. Every write goes through a **preview with a confirm button**; nothing is saved until the author presses it.

| Command | What it does |
|---|---|
| `!aclinic update <raw notes>` | Daily Summary row (Current Update / Latest Status / Priority / Blockers / Confirm to Client). Claude sees yesterday's row, so a silent "Latest Status" carries over. |
| `!aclinic note <raw request>` | Project Notes row, auto-numbered |
| `!aclinic task <what needs doing>` | Notion task: title, due date ("by friday" → real date), priority, notes |
| `!aclinic status` | Show the latest Daily Summary row |

Examples:
```
!aclinic update price-list content done, lhala-doctor QA still going, need client to confirm bestshot slug
!aclinic task re-test concealer-shot page before Monday, high priority
```

---

## Setup (about 30 minutes, once)

### 1. Discord
1. https://discord.com/developers/applications → **New Application**.
2. **Bot** tab → **Reset Token** → copy it into `DISCORD_TOKEN`.
3. Same tab → **Privileged Gateway Intents** → turn on **Message Content Intent** (without this, `!` commands silently do nothing).
4. **OAuth2 → URL Generator** → scope `bot` → permissions: View Channels, Send Messages, Embed Links, Read Message History → open the URL and invite the bot to your server.
5. Optional: enable Developer Mode (Discord settings → Advanced), right-click your channel → Copy Channel ID → `ALLOWED_CHANNEL_ID` to restrict the bot to that channel.

### 2. Google Sheets
1. https://console.cloud.google.com → create/select a project → **APIs & Services → Library → Google Sheets API → Enable**.
2. **IAM & Admin → Service Accounts → Create**. Then open it → **Keys → Add key → JSON**. A file downloads.
3. Open your Google Sheet → **Share** → paste the service account email (`xxx@xxx.iam.gserviceaccount.com`) → **Editor**.
4. `SPREADSHEET_ID` is the long string in the sheet URL: `docs.google.com/spreadsheets/d/<THIS>/edit`.
5. Locally: save the JSON as `service_account.json`. On a host: paste the whole file contents into `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`.

The `Daily Summary` and `Project Notes` tabs and their headers are created automatically.

### 3. Notion (for `!aclinic task`)
1. https://www.notion.so/profile/integrations → **New integration** → type Internal → copy the secret into `NOTION_TOKEN`.
2. Open your tasks database in Notion → `...` menu → **Connections** → add your integration. **Skip this and you get a 404**; Notion hides anything not shared with the integration.
3. `NOTION_DATABASE_ID`: open the database as a full page; the URL is `notion.so/<workspace>/<THIS 32-char id>?v=...`.
4. The bot finds the title property itself. It also fills **Due** (date), **Priority** (select/status) if they exist with those names; if yours are named differently, set `NOTION_DUE_PROP` / `NOTION_PRIORITY_PROP`. Priority values must already exist as options (High / Medium / Low); the bot never creates new options.

### 4. Anthropic
Create a key at https://console.anthropic.com → `ANTHROPIC_API_KEY`. Default model is Haiku 5.5; cost at daily-standup volume is pennies per month.

### 5. Run locally first
```bash
cp .env.example .env    # fill it in
pip install -r requirements.txt
python bot.py
```
Try `!aclinic status` in your channel, then an `update`. Fix problems here, not on the server.

---

## Deploy

The bot is a long-running **worker**, not a web server (no port, no URL).

**Recommended: Railway** (~$5/mo Hobby plan; the old free tier is gone).
1. Push this repo to GitHub (private).
2. railway.com → **New Project → Deploy from GitHub repo**. The included `Procfile` (`worker: python bot.py`) sets the start command.
3. **Variables** tab: add everything from `.env.example`. For Google use `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT` (paste the full JSON); leave the file-path var unset.
4. Deploy; logs should show `Bot ready: ...`.

Alternatives: a $4-6 VPS (Hetzner/DigitalOcean) running it under `systemd` if you want full control; Fly.io works too. Avoid Render's free tier: free web services sleep, and this bot has no port to keep it awake.

## Security notes
- Never commit `.env` or the service account JSON (both are gitignored). If a token was ever pasted in chat or a zip, rotate it.
- Anyone in the allowed channel can run commands, and Claude calls cost money. Use `ALLOWED_CHANNEL_ID` and a private channel.
- Sheet values are written as `RAW`, so text starting with `=` can't become a formula.

Tests: `pytest`.

# A Clinic Bot

Discord bot that turns raw notes into structured rows in Google Sheets, using Claude to write the summary.

```
!aclinic update price-list content done, lhala-doctor QA still going, need client to confirm bestshot slug
```

1. Claude extracts Current Update / Latest Status / Priority Today / Blockers / Confirm to Client (it sees the previous row, so a silent "Latest Status" carries over).
2. The bot posts a **preview** with Save / Cancel buttons. Nothing touches the sheet until the author presses Save.
3. Save appends a row to the `Daily Summary` tab.

| Command | What it does |
|---|---|
| `!aclinic update <raw notes>` | Daily Summary row (preview → save) |
| `!aclinic note <raw request/notes>` | Project Notes row, auto-numbered (preview → save) |
| `!aclinic status` | Show the latest Daily Summary row |

## Setup

**Discord**: Developer Portal → New Application → Bot → copy token, and turn on **Message Content Intent** (required for `!` commands). Invite with scope `bot`, permissions Send Messages, Embed Links, Read Message History.

**Google**: Cloud Console → enable Sheets API → create a service account → JSON key. Share the sheet with the service account email as Editor. Tabs/headers are created automatically.

**Anthropic**: create an API key at console.anthropic.com.

```bash
cp .env.example .env   # fill in DISCORD_TOKEN, ANTHROPIC_API_KEY, SPREADSHEET_ID, service account
pip install -r requirements.txt
python bot.py
```

## Hosting

The bot is a long-running worker, not a web server.
- **Railway**: deploy from GitHub, start command `python bot.py`, set env vars, paste the whole key JSON into `GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT`. Railway no longer has a truly free tier (a trial, then ~$5/mo), which is plenty for this.
- **Render**: free *web* services sleep and expect a port; use a paid Background Worker.
- Any $4-5 VPS with `systemd` or Docker works too.

Cost of the Claude calls with the default Haiku model is negligible for daily use.

## Notes

- Values are written with `RAW` mode, so text starting with `=` can't become a sheet formula.
- Set `ALLOWED_CHANNEL_ID` to restrict the bot to one channel.
- Tests: `pytest`.

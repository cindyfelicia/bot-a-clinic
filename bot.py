import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

from sheets import SheetsClient  # noqa: E402  (after load_dotenv so env is populated)
from notion import NotionTasks  # noqa: E402
from summarizer import Summarizer  # noqa: E402

PREFIX = os.getenv("COMMAND_PREFIX", "!aclinic")
ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID") or 0)
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Makassar"))
CONFIRM_TIMEOUT = 300  # seconds

intents = discord.Intents.default()
intents.message_content = True  # privileged: enable "Message Content Intent" in the Developer Portal
bot = commands.Bot(command_prefix=PREFIX + " ", intents=intents, help_command=None, case_insensitive=True)

sheets: SheetsClient | None = None
summarizer: Summarizer | None = None
notion: NotionTasks | None = None


def today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def clip(s: str, n: int = 1000) -> str:
    return (s or "-")[:n]


class ConfirmView(discord.ui.View):
    """Preview → Save / Cancel. Only the author can press; nothing hits the sheet until Save."""

    def __init__(self, author: discord.abc.User, save_coro, done_embed_fn, label: str = "Save to sheet"):
        super().__init__(timeout=CONFIRM_TIMEOUT)
        self.save.label = label
        self.author = author
        self.save_coro = save_coro
        self.done_embed_fn = done_embed_fn
        self.message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Only the person who ran the command can confirm.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Save to sheet", style=discord.ButtonStyle.success, emoji="✅")
    async def save(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.defer()
        try:
            result = await self.save_coro()
        except Exception as e:  # sheet/API failure: leave the preview so they can retry
            await interaction.followup.send(f"❌ Failed to write to sheet: `{e}`")
            return
        await interaction.edit_original_response(embed=self.done_embed_fn(result), view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="Cancelled. Nothing was written.", embed=None, view=None)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(content="Timed out. Nothing was written.", embed=None, view=None)
            except discord.HTTPException:
                pass


def daily_embed(d: dict, date: str, title: str, color: int, footer: str) -> discord.Embed:
    e = discord.Embed(title=title, color=color)
    e.add_field(name="📅 Date", value=date, inline=True)
    e.add_field(name="📋 Current Update", value=clip(d["current_update"]), inline=False)
    e.add_field(name="🔵 Latest Status", value=clip(d["latest_status"]), inline=False)
    e.add_field(name="🎯 Priority Today", value=clip(d["priority_today"]), inline=False)
    e.add_field(name="🚧 Blockers", value=clip(d["blockers"]), inline=False)
    e.add_field(name="❓ Confirm to Client", value=clip(d["confirm_client"]), inline=False)
    e.set_footer(text=footer)
    return e


def note_embed(n: dict, date_req: str, date_res: str, title: str, color: int, footer: str) -> discord.Embed:
    e = discord.Embed(title=title, color=color)
    e.add_field(name="📅 Date Request", value=date_req, inline=True)
    e.add_field(name="✅ Date Resolve", value=date_res, inline=True)
    e.add_field(name="🏷️ Status", value=clip(n["status"]), inline=True)
    e.add_field(name="💬 Client Request", value=clip(n["client_request"]), inline=False)
    e.add_field(name="🔧 Action Taken", value=clip(n["action_taken"]), inline=False)
    e.set_footer(text=footer)
    return e


@bot.check
async def only_allowed_channel(ctx: commands.Context) -> bool:
    return not ALLOWED_CHANNEL_ID or ctx.channel.id == ALLOWED_CHANNEL_ID


@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user} | prefix: '{PREFIX} <update|note|task|status>'")


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, (commands.CheckFailure, commands.CommandNotFound)):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(f"Add some text after the command, e.g. `{PREFIX} {ctx.command.name} <what happened>`")
        return
    raise error


@bot.command(name="update")
async def update(ctx: commands.Context, *, raw: str):
    """Paste raw notes; Claude structures them into a Daily Summary row."""
    async with ctx.typing():
        try:
            previous = await asyncio.to_thread(sheets.get_latest_daily_summary)
            d = await summarizer.daily(raw, previous)
        except Exception as e:
            await ctx.reply(f"❌ Couldn't generate the summary: `{e}`")
            return

    date = today()
    row = [date, d["current_update"], d["latest_status"], d["priority_today"], d["blockers"], d["confirm_client"]]

    async def save():
        await asyncio.to_thread(sheets.append_daily_summary, row)

    view = ConfirmView(
        ctx.author, save,
        lambda _: daily_embed(d, date, "✅ Daily Update Saved", 0x00C49A, f"Added by {ctx.author.display_name}"),
    )
    view.message = await ctx.reply(
        embed=daily_embed(d, date, "📝 Preview — Daily Update", 0xF59E0B, "Nothing is saved until you press Save"),
        view=view,
    )


@bot.command(name="note")
async def note(ctx: commands.Context, *, raw: str):
    """Paste a client request / project note; Claude structures it into a Project Notes row."""
    async with ctx.typing():
        try:
            n = await summarizer.note(raw)
        except Exception as e:
            await ctx.reply(f"❌ Couldn't generate the note: `{e}`")
            return

    date_req = n["date_request"] or today()
    date_res = n["date_resolve"] or "-"

    async def save() -> int:
        return await asyncio.to_thread(
            sheets.append_project_note, [date_req, date_res, n["client_request"], n["action_taken"], n["status"]]
        )

    view = ConfirmView(
        ctx.author, save,
        lambda num: note_embed(n, date_req, date_res, f"📝 Project Note #{num} Saved", 0x5865F2, f"Added by {ctx.author.display_name}"),
    )
    view.message = await ctx.reply(
        embed=note_embed(n, date_req, date_res, "📝 Preview — Project Note", 0xF59E0B, "Nothing is saved until you press Save"),
        view=view,
    )


def task_embed(t: dict, title: str, color: int, footer: str, url: str = "") -> discord.Embed:
    e = discord.Embed(title=title, color=color, url=url or None)
    e.add_field(name="✔️ Task", value=clip(t["title"]), inline=False)
    e.add_field(name="📅 Due", value=t["due"] or "-", inline=True)
    e.add_field(name="🔥 Priority", value=t["priority"] or "-", inline=True)
    if t["notes"]:
        e.add_field(name="🗒️ Notes", value=clip(t["notes"]), inline=False)
    e.set_footer(text=footer)
    return e


@bot.command(name="task")
async def task(ctx: commands.Context, *, raw: str):
    """Describe a task in plain words; Claude structures it and creates it in Notion."""
    if notion is None:
        await ctx.reply("Notion isn't configured (set `NOTION_TOKEN` and `NOTION_DATABASE_ID`).")
        return
    async with ctx.typing():
        try:
            t = await summarizer.task(raw, today())
        except Exception as e:
            await ctx.reply(f"❌ Couldn't parse the task: `{e}`")
            return

    async def save() -> str:
        return await asyncio.to_thread(
            notion.create_task, t["title"], t["due"], t["priority"], "", f"{t['notes']}\n\nCreated from Discord by {ctx.author.display_name}".strip()
        )

    view = ConfirmView(
        ctx.author, save,
        lambda url: task_embed(t, "✅ Task Created in Notion", 0x00C49A, f"Added by {ctx.author.display_name}", url),
        label="Create in Notion",
    )
    view.message = await ctx.reply(
        embed=task_embed(t, "📝 Preview — Notion Task", 0xF59E0B, "Nothing is created until you press the button"),
        view=view,
    )


@bot.command(name="status")
async def status(ctx: commands.Context):
    """Show the latest Daily Summary row."""
    try:
        latest = await asyncio.to_thread(sheets.get_latest_daily_summary)
    except Exception as e:
        await ctx.reply(f"❌ Error: `{e}`")
        return
    if not latest:
        await ctx.reply(f"No entries yet. Use `{PREFIX} update <notes>` to add one.")
        return
    latest = latest + [""] * (6 - len(latest))
    d = dict(zip(["current_update", "latest_status", "priority_today", "blockers", "confirm_client"], latest[1:6]))
    await ctx.reply(embed=daily_embed(d, latest[0], "📊 A Clinic — Latest Status", 0xF59E0B, "From Google Sheets"))


def main():
    global sheets, summarizer, notion
    sheets = SheetsClient(os.environ["SPREADSHEET_ID"])
    summarizer = Summarizer()
    if os.getenv("NOTION_TOKEN") and os.getenv("NOTION_DATABASE_ID"):
        notion = NotionTasks(os.environ["NOTION_TOKEN"], os.environ["NOTION_DATABASE_ID"])
    bot.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    main()

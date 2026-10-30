import json
import os

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

DAILY_SHEET = "Daily Summary"
NOTES_SHEET = "Project Notes"

DAILY_HEADERS = ["Date", "Current Update", "Latest Status", "Priority Today", "Blockers", "Confirm to Client"]
NOTES_HEADERS = ["#", "Date Request", "Date Resolve", "Client Request", "Action Taken", "Status"]


def _credentials() -> Credentials:
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json"), scopes=SCOPES
    )


class SheetsClient:
    """Blocking client; call from async code via asyncio.to_thread."""

    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        self.service = build("sheets", "v4", credentials=_credentials(), cache_discovery=False)
        self.sheet = self.service.spreadsheets()
        self._ensure_sheets()

    def _ensure_sheets(self):
        meta = self.sheet.get(spreadsheetId=self.spreadsheet_id).execute()
        existing = {s["properties"]["title"] for s in meta["sheets"]}
        requests = [
            {"addSheet": {"properties": {"title": t}}}
            for t in (DAILY_SHEET, NOTES_SHEET)
            if t not in existing
        ]
        if requests:
            self.sheet.batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests}).execute()
        self._write_header_if_empty(DAILY_SHEET, DAILY_HEADERS)
        self._write_header_if_empty(NOTES_SHEET, NOTES_HEADERS)

    def _write_header_if_empty(self, tab: str, headers: list):
        result = self.sheet.values().get(spreadsheetId=self.spreadsheet_id, range=f"{tab}!A1:Z1").execute()
        if not result.get("values"):
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{tab}!A1",
                valueInputOption="RAW",
                body={"values": [headers]},
            ).execute()

    def _append(self, tab: str, row: list):
        # RAW so a model/user string starting with "=" can never become a formula.
        self.sheet.values().append(
            spreadsheetId=self.spreadsheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    def append_daily_summary(self, row: list):
        self._append(DAILY_SHEET, row)

    def append_project_note(self, row: list) -> int:
        """Append a note, auto-numbering from the highest existing # (robust to deleted rows)."""
        col = self.sheet.values().get(spreadsheetId=self.spreadsheet_id, range=f"{NOTES_SHEET}!A2:A").execute()
        nums = [int(v[0]) for v in col.get("values", []) if v and str(v[0]).isdigit()]
        number = max(nums, default=0) + 1
        self._append(NOTES_SHEET, [number] + row)
        return number

    def get_latest_daily_summary(self) -> list | None:
        result = self.sheet.values().get(spreadsheetId=self.spreadsheet_id, range=f"{DAILY_SHEET}!A:F").execute()
        rows = result.get("values", [])
        return rows[-1] if len(rows) > 1 else None

"""Minimal Notion client: create a task page in a database. Blocking; call via asyncio.to_thread."""
import os

import httpx

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"

PRIORITY_PROP = os.getenv("NOTION_PRIORITY_PROP", "Priority")
DUE_PROP = os.getenv("NOTION_DUE_PROP", "Due")
STATUS_PROP = os.getenv("NOTION_STATUS_PROP", "Status")


class NotionTasks:
    def __init__(self, token: str, database_id: str):
        self.database_id = database_id
        self.http = httpx.Client(
            base_url=API,
            headers={"Authorization": f"Bearer {token}", "Notion-Version": VERSION},
            timeout=20,
        )
        db = self._check(self.http.get(f"/databases/{database_id}"))
        self.props = db["properties"]
        self.title_prop = next(k for k, v in self.props.items() if v["type"] == "title")

    @staticmethod
    def _check(resp: httpx.Response) -> dict:
        if resp.status_code >= 400:
            raise RuntimeError(f"Notion {resp.status_code}: {resp.json().get('message', resp.text)}")
        return resp.json()

    def _option(self, prop: str, wanted: str) -> str | None:
        """Match `wanted` to an existing select/status option (case-insensitive); never invents options."""
        p = self.props.get(prop)
        if not p or p["type"] not in ("select", "status"):
            return None
        for o in p[p["type"]]["options"]:
            if o["name"].lower() == wanted.lower():
                return o["name"]
        return None

    def create_task(self, title: str, due: str = "", priority: str = "", status: str = "", notes: str = "") -> str:
        props: dict = {self.title_prop: {"title": [{"text": {"content": title[:200]}}]}}
        if due and DUE_PROP in self.props and self.props[DUE_PROP]["type"] == "date":
            props[DUE_PROP] = {"date": {"start": due}}
        if (name := self._option(PRIORITY_PROP, priority)) and priority:
            props[PRIORITY_PROP] = {self.props[PRIORITY_PROP]["type"]: {"name": name}}
        if (name := self._option(STATUS_PROP, status)) and status:
            props[STATUS_PROP] = {self.props[STATUS_PROP]["type"]: {"name": name}}

        body: dict = {"parent": {"database_id": self.database_id}, "properties": props}
        if notes:
            body["children"] = [{
                "object": "block", "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": notes[:2000]}}]},
            }]
        return self._check(self.http.post("/pages", json=body))["url"]

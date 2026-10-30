import asyncio
from types import SimpleNamespace

import summarizer as s


class FakeMessages:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        data = {k: f" {k} " for k in kwargs["tools"][0]["input_schema"]["required"]}
        return SimpleNamespace(content=[SimpleNamespace(type="tool_use", input=data)])


def make():
    sm = s.Summarizer.__new__(s.Summarizer)
    sm.client = SimpleNamespace(messages=FakeMessages())
    return sm


def test_daily_forces_tool_and_strips():
    sm = make()
    out = asyncio.run(sm.daily("did stuff", ["2026-10-29", "a", "b", "c", "d", "e"]))
    kw = sm.client.messages.kwargs
    assert kw["tool_choice"] == {"type": "tool", "name": "record_daily_update"}
    assert "<previous_entry>" in kw["messages"][0]["content"]
    assert out["blockers"] == "blockers"


def test_note_has_no_previous_context():
    sm = make()
    out = asyncio.run(sm.note("client wants X"))
    assert "<previous_entry>" not in sm.client.messages.kwargs["messages"][0]["content"]
    assert out["status"] == "status"


def test_task_includes_today():
    sm = make()
    out = asyncio.run(sm.task("fix login by friday", "2026-10-30"))
    assert "2026-10-30" in sm.client.messages.kwargs["messages"][0]["content"]
    assert out["title"] == "title"

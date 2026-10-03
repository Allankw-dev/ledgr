"""The Claude path must behave exactly as it did before the provider layer existed."""

from types import SimpleNamespace

from app.core.config import settings
from app.services import llm


class FakeClient:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        return self.replies.pop(0)


def _msg(stop, *blocks):
    return SimpleNamespace(stop_reason=stop, content=list(blocks))


def test_claude_tool_loop(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    monkeypatch.setattr(settings, "ai_provider", "auto")
    tool_block = SimpleNamespace(type="tool_use", id="tu_1", name="get_summary_stats", input={})
    client = FakeClient([_msg("tool_use", tool_block), _msg("end_turn", SimpleNamespace(type="text", text="All good."))])
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", lambda api_key: client)

    out = llm.run_tool_conversation(
        system="sys", messages=[{"role": "user", "content": "hi"}],
        tools=[{"name": "get_summary_stats", "description": "d", "input_schema": {"type": "object", "properties": {}}}],
        run_tool=lambda n, i: '{"collected": 5}', max_iterations=4,
    )
    assert out == "All good."
    assert client.calls[0]["model"] == settings.anthropic_model and client.calls[0]["system"] == "sys"
    result = client.calls[1]["messages"][-1]["content"][0]
    assert result == {"type": "tool_result", "tool_use_id": "tu_1", "content": '{"collected": 5}'}

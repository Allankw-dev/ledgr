"""Gemini provider: request shape, tool loop, error handling. No network — httpx.MockTransport."""

import json

import httpx
import pytest

from app.core.config import settings
from app.services import llm

TOOLS = [
    {"name": "get_summary_stats", "description": "Totals.", "input_schema": {"type": "object", "properties": {}}},
    {
        "name": "get_overdue_invoices",
        "description": "Overdue list.",
        "input_schema": {
            "type": "object",
            "properties": {"class_name": {"type": "string", "description": "e.g. Grade 4"}, "limit": {"type": "integer"}},
            "required": ["class_name"],
            "additionalProperties": False,
        },
    },
]


@pytest.fixture(autouse=True)
def _gemini(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-test-model")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "ai_provider", "auto")
    monkeypatch.setattr(llm, "_resolved_gemini_model", None)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    yield
    monkeypatch.setattr(llm, "_transport", None)


def _serve(monkeypatch, handler):
    monkeypatch.setattr(llm, "_transport", httpx.MockTransport(handler))


def _text(t):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": t}]}, "finishReason": "STOP"}]}


def _ask(**kw):
    return llm.run_tool_conversation(
        system="sys", messages=[{"role": "user", "content": "hi"}], tools=TOOLS,
        run_tool=kw.pop("run_tool", lambda n, i: "{}"), max_iterations=kw.pop("max_iterations", 4),
    )


# ---- provider choice ---------------------------------------------------------


def test_provider_selection(monkeypatch):
    assert llm.active_provider() == "gemini"
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant")
    assert llm.active_provider() == "gemini"  # auto prefers the free one
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    assert llm.active_provider() == "anthropic"
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "ai_provider", "auto")
    assert llm.active_provider() == "anthropic"
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    assert llm.active_provider() is None
    assert _ask() is None  # nothing configured -> caller shows its own message


def test_forcing_a_provider_without_its_key_means_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    assert llm.active_provider() is None


# ---- request shape -----------------------------------------------------------


def test_tools_converted_to_gemini_format():
    [group] = llm.to_gemini_tools(TOOLS)
    by_name = {d["name"]: d for d in group["functionDeclarations"]}
    assert "parameters" not in by_name["get_summary_stats"]  # Gemini rejects an empty OBJECT schema
    params = by_name["get_overdue_invoices"]["parameters"]
    assert params["type"] == "OBJECT"
    assert params["properties"]["limit"]["type"] == "INTEGER"
    assert params["required"] == ["class_name"]
    assert "additionalProperties" not in params
    # a property that happens to be NAMED like a schema keyword must survive
    [g2] = llm.to_gemini_tools([{"name": "t", "description": "d", "input_schema": {"type": "object", "properties": {"type": {"type": "string"}, "enum": {"type": "string"}}}}])
    assert set(g2["functionDeclarations"][0]["parameters"]["properties"]) == {"type", "enum"}


def test_request_is_well_formed_and_key_goes_in_a_header_not_the_url(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
        return httpx.Response(200, json=_text("Hello!"))

    _serve(monkeypatch, handler)
    out = llm.run_tool_conversation(
        system="You are helpful.",
        messages=[{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}, {"role": "user", "content": "q2"}],
        tools=TOOLS, run_tool=lambda n, i: "{}", max_iterations=4,
    )
    assert out == "Hello!"
    assert seen["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-test-model:generateContent"
    assert "test-key" not in seen["url"] and seen["headers"]["x-goog-api-key"] == "test-key"
    body = seen["body"]
    assert body["systemInstruction"]["parts"][0]["text"] == "You are helpful."
    assert [c["role"] for c in body["contents"]] == ["user", "model", "user"]  # assistant -> model
    assert body["generationConfig"]["maxOutputTokens"] >= 4096


# ---- tool loop ---------------------------------------------------------------


def test_tool_call_is_run_and_result_sent_back_with_the_models_own_turn(monkeypatch):
    requests = []
    model_turn = {"role": "model", "parts": [
        {"functionCall": {"name": "get_overdue_invoices", "args": {"class_name": "Grade 4", "limit": 5}}, "thoughtSignature": "OPAQUE-SIG"}]}

    def handler(request):
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(200, json={"candidates": [{"content": model_turn}]})
        return httpx.Response(200, json=_text("Two students are overdue."))

    _serve(monkeypatch, handler)
    ran = []

    def run_tool(name, args):
        ran.append((name, args))
        return json.dumps({"count": 2, "students": ["A", "B"]})

    assert _ask(run_tool=run_tool) == "Two students are overdue."
    assert ran == [("get_overdue_invoices", {"class_name": "Grade 4", "limit": 5})]
    second = requests[1]["contents"]
    assert second[-2] == model_turn  # echoed back verbatim, thoughtSignature included
    fr = second[-1]["parts"][0]["functionResponse"]
    assert second[-1]["role"] == "user" and fr["name"] == "get_overdue_invoices"
    assert fr["response"] == {"count": 2, "students": ["A", "B"]}


def test_list_and_non_json_tool_results_are_wrapped_in_an_object(monkeypatch):
    assert llm._function_response_body(json.dumps([1, 2])) == {"result": [1, 2]}
    assert llm._function_response_body("plain words") == {"result": "plain words"}
    assert llm._function_response_body(json.dumps({"a": 1})) == {"a": 1}


def test_parallel_tool_calls_all_answered_in_one_turn(monkeypatch):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [
                {"functionCall": {"name": "get_summary_stats", "args": {}}},
                {"functionCall": {"name": "get_overdue_invoices", "args": {"class_name": "Grade 1"}}}]}}]})
        sent = json.loads(request.content)["contents"][-1]["parts"]
        assert len(sent) == 2
        return httpx.Response(200, json=_text("done"))

    _serve(monkeypatch, handler)
    assert _ask() == "done"


def test_endless_tool_calling_is_cut_off(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": "get_summary_stats", "args": {}}}]}}]})

    _serve(monkeypatch, handler)
    assert _ask(max_iterations=3) == llm.TOO_LONG_MESSAGE


def test_thinking_parts_are_not_shown_to_the_user(monkeypatch):
    _serve(monkeypatch, lambda r: httpx.Response(200, json={"candidates": [{"content": {"role": "model", "parts": [
        {"text": "internal reasoning", "thought": True}, {"text": "The answer."}]}}]}))
    assert _ask() == "The answer."


# ---- failures become friendly replies, never a 500 ----------------------------


def test_rate_limit_gives_a_friendly_message(monkeypatch):
    _serve(monkeypatch, lambda r: httpx.Response(429, json={"error": {"message": "quota"}}))
    assert _ask() == llm.BUSY_MESSAGE


def test_bad_key_and_server_errors_give_a_friendly_message(monkeypatch):
    _serve(monkeypatch, lambda r: httpx.Response(403, json={"error": {"message": "API key not valid"}}))
    assert _ask() == llm.UNAVAILABLE_MESSAGE
    _serve(monkeypatch, lambda r: httpx.Response(503, text="overloaded"))
    assert _ask() == llm.UNAVAILABLE_MESSAGE


def test_transient_503_is_retried_once(monkeypatch):
    n = {"c": 0}

    def handler(request):
        n["c"] += 1
        return httpx.Response(503, text="try later") if n["c"] == 1 else httpx.Response(200, json=_text("ok"))

    _serve(monkeypatch, handler)
    assert _ask() == "ok" and n["c"] == 2


def test_network_failure_gives_a_friendly_message(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("no route")

    _serve(monkeypatch, handler)
    assert _ask() == llm.UNAVAILABLE_MESSAGE


def test_blocked_or_empty_answer_does_not_crash(monkeypatch):
    _serve(monkeypatch, lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    assert "rephras" in _ask()
    _serve(monkeypatch, lambda r: httpx.Response(200, json={"candidates": [{"finishReason": "MAX_TOKENS", "content": {"role": "model"}}]}))
    assert "rephras" in _ask()


# ---- retired model: find a working one instead of breaking -------------------

MODELS = {"models": [
    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.9-flash-preview", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.6-flash-image", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.1-flash-live-preview", "supportedGenerationMethods": ["bidiGenerateContent"]},
    {"name": "models/gemini-embedding-2", "supportedGenerationMethods": ["embedContent"]},
    {"name": "models/gemini-3.1-pro", "supportedGenerationMethods": ["generateContent"]},
]}


def test_replacement_model_choice():
    assert llm._pick_replacement_model(MODELS["models"]) == "gemini-3.5-flash-lite"  # newest non-preview Flash-Lite
    no_lite = [m for m in MODELS["models"] if "lite" not in m["name"]]
    assert llm._pick_replacement_model(no_lite) == "gemini-3.6-flash"
    assert llm._pick_replacement_model([]) is None


def test_retired_model_404_discovers_a_working_one_and_remembers_it(monkeypatch):
    used = []

    def handler(request):
        if request.url.path.endswith("/models") and request.method == "GET":
            return httpx.Response(200, json=MODELS)
        used.append(request.url.path.split("/models/")[1].split(":")[0])
        if used[-1] == "gemini-test-model":
            return httpx.Response(404, json={"error": {"message": "model not found"}})
        return httpx.Response(200, json=_text("works"))

    _serve(monkeypatch, handler)
    assert _ask() == "works"
    assert used == ["gemini-test-model", "gemini-3.5-flash-lite"]
    assert _ask() == "works"
    assert used[-1] == "gemini-3.5-flash-lite" and used.count("gemini-test-model") == 1  # not retried every request


def test_404_with_nothing_to_fall_back_to_is_a_friendly_message(monkeypatch):
    _serve(monkeypatch, lambda r: httpx.Response(200, json={"models": []}) if r.method == "GET" else httpx.Response(404, json={}))
    assert _ask() == llm.UNAVAILABLE_MESSAGE

"""One place that talks to the AI provider, so the two assistants (bursar + parent)
don't care whether Gemini or Claude is behind them.

Both assistants run the same loop: send the conversation + their tools, and if the
model asks to call a tool, run it, hand the result back, repeat until it answers in
plain text. `run_tool_conversation` does that for either provider.

Provider choice (settings.ai_provider): "auto" = Gemini if GEMINI_API_KEY is set,
else Claude if ANTHROPIC_API_KEY is set; or force "gemini" / "anthropic".

Failures (rate limit on a free key, provider outage, a retired model) are logged and
turned into a short, friendly reply instead of a 500 — the assistant is a convenience
and must never take a page down with it.
"""

import json
import logging
import time
from typing import Callable

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
BUSY_MESSAGE = "The assistant is busy right now — please try again in a minute."
UNAVAILABLE_MESSAGE = "The assistant isn't available right now — please try again later."
TOO_LONG_MESSAGE = "That took more lookups than expected — try asking a more specific question."

# Tests swap this for an httpx.MockTransport; production leaves it None.
_transport: httpx.BaseTransport | None = None
# The model name that actually works (set if the configured one had to be replaced).
_resolved_gemini_model: str | None = None

ToolRunner = Callable[[str, dict], str]


def active_provider() -> str | None:
    pref = (settings.ai_provider or "auto").strip().lower()
    if pref == "gemini":
        return "gemini" if settings.gemini_api_key else None
    if pref == "anthropic":
        return "anthropic" if settings.anthropic_api_key else None
    if settings.gemini_api_key:
        return "gemini"
    if settings.anthropic_api_key:
        return "anthropic"
    return None


def run_tool_conversation(
    *,
    system: str,
    messages: list[dict],
    tools: list[dict],
    run_tool: ToolRunner,
    max_iterations: int,
    max_tokens: int = 1024,
) -> str | None:
    """Returns the assistant's reply, or None when no provider is configured (the
    caller then shows its own "not set up yet" message).

    `messages`: [{"role": "user"|"assistant", "content": str}, ...] — the full history.
    `tools`: Anthropic-style [{"name", "description", "input_schema"}] (converted for Gemini).
    `run_tool(name, input) -> str`: executes a tool and returns its result as a JSON string."""
    provider = active_provider()
    if provider == "gemini":
        return _run_gemini(system, messages, tools, run_tool, max_iterations, max_tokens)
    if provider == "anthropic":
        return _run_anthropic(system, messages, tools, run_tool, max_iterations, max_tokens)
    return None


# --------------------------------------------------------------------------- Gemini

_SCHEMA_KEYS = {"type", "description", "properties", "items", "enum", "required", "format", "nullable"}


def _gemini_schema(node):
    """Anthropic/JSON-Schema -> the subset Gemini accepts: upper-case type names and
    no unknown keys."""
    if isinstance(node, list):
        return [_gemini_schema(n) for n in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for key, value in node.items():
        if key == "properties":  # a map of property-name -> schema; the names are not schema keywords
            out[key] = {name: _gemini_schema(sub) for name, sub in value.items()}
        elif key in _SCHEMA_KEYS:
            out[key] = value.upper() if key == "type" and isinstance(value, str) else _gemini_schema(value)
    return out


def to_gemini_tools(tools: list[dict]) -> list[dict]:
    declarations = []
    for tool in tools:
        decl = {"name": tool["name"], "description": tool.get("description", "")}
        schema = tool.get("input_schema") or {}
        # Gemini rejects an OBJECT with no properties, so a no-argument tool omits `parameters`.
        if schema.get("properties"):
            decl["parameters"] = _gemini_schema(schema)
        declarations.append(decl)
    return [{"functionDeclarations": declarations}]


def _function_response_body(output: str) -> dict:
    """Gemini wants the tool result as a JSON OBJECT."""
    try:
        parsed = json.loads(output)
    except (TypeError, ValueError):
        return {"result": output}
    return parsed if isinstance(parsed, dict) else {"result": parsed}


def _gemini_model() -> str:
    return _resolved_gemini_model or settings.gemini_model


def _pick_replacement_model(models: list[dict]) -> str | None:
    """From a ListModels response, the best current general-purpose Flash model:
    supports generateContent, not a preview/experimental build, not an image/audio/live/
    embedding variant. Prefers Flash-Lite (cheapest, friendliest free quota) over Flash."""
    skip = ("preview", "exp", "image", "tts", "live", "audio", "embedding", "vision", "robotics", "computer", "omni", "thinking", "-latest")
    candidates = []
    for m in models:
        name = (m.get("name") or "").removeprefix("models/")
        if "generateContent" not in (m.get("supportedGenerationMethods") or []):
            continue
        if not name.startswith("gemini-") or "flash" not in name or any(t in name for t in skip):
            continue
        candidates.append(name)
    if not candidates:
        return None

    def version(name: str) -> list[int]:  # gemini-3.1-flash-lite -> [3, 1]
        before_flash = name.split("flash")[0]
        return [int(n) for n in "".join(c if c.isdigit() else " " for c in before_flash).split()]

    lite = [c for c in candidates if "lite" in c]
    return max(lite or candidates, key=version)


def _gemini_post(client: httpx.Client, model: str, body: dict) -> httpx.Response:
    url = f"{GEMINI_BASE}/models/{model}:generateContent"
    headers = {"x-goog-api-key": settings.gemini_api_key or "", "content-type": "application/json"}
    response = client.post(url, headers=headers, content=json.dumps(body))
    if response.status_code in (500, 502, 503, 504):  # transient on Google's side: one more try
        time.sleep(1.5)
        response = client.post(url, headers=headers, content=json.dumps(body))
    return response


def _discover_working_model(client: httpx.Client) -> str | None:
    response = client.get(f"{GEMINI_BASE}/models", headers={"x-goog-api-key": settings.gemini_api_key or ""},
                          params={"pageSize": 1000})
    if response.status_code != 200:
        return None
    return _pick_replacement_model(response.json().get("models", []))


def _run_gemini(system, messages, tools, run_tool, max_iterations, max_tokens) -> str:
    global _resolved_gemini_model

    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "tools": to_gemini_tools(tools),
        # Newer Gemini models "think" first and thinking tokens count against this cap,
        # so it is generous: a tight cap yields an empty answer.
        "generationConfig": {"maxOutputTokens": max(max_tokens * 4, 4096), "temperature": 0.3},
    }

    try:
        with httpx.Client(timeout=45.0, transport=_transport) as client:
            for _ in range(max_iterations):
                response = _gemini_post(client, _gemini_model(), body)

                if response.status_code == 404 and _resolved_gemini_model is None:
                    replacement = _discover_working_model(client)
                    if replacement:
                        logger.warning(
                            "Gemini model %r is not available any more; using %r instead. "
                            "Set GEMINI_MODEL=%s to make this permanent.", settings.gemini_model, replacement, replacement)
                        _resolved_gemini_model = replacement
                        response = _gemini_post(client, replacement, body)

                if response.status_code == 429:
                    logger.warning("Gemini rate limit / quota hit: %s", response.text[:300])
                    return BUSY_MESSAGE
                if response.status_code != 200:
                    logger.error("Gemini request failed (%s): %s", response.status_code, response.text[:500])
                    return UNAVAILABLE_MESSAGE

                data = response.json()
                candidate = (data.get("candidates") or [None])[0]
                content = (candidate or {}).get("content") or {}
                parts = content.get("parts") or []

                if not candidate or not parts:
                    reason = (data.get("promptFeedback") or {}).get("blockReason") or (candidate or {}).get("finishReason")
                    logger.warning("Gemini returned no answer (reason=%s)", reason)
                    return "I couldn't answer that one — try rephrasing your question."

                calls = [p["functionCall"] for p in parts if "functionCall" in p]
                if not calls:
                    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                    return text.strip() or "I couldn't put an answer together — try rephrasing your question."

                # Hand the model's turn back EXACTLY as received (newer models attach an opaque
                # thoughtSignature to their function calls and require it on the next request).
                contents.append(content)
                contents.append({
                    "role": "user",
                    "parts": [
                        {"functionResponse": {"name": call["name"], "response": _function_response_body(run_tool(call["name"], call.get("args") or {}))}}
                        for call in calls
                    ],
                })
            return TOO_LONG_MESSAGE
    except httpx.HTTPError as exc:
        logger.error("Could not reach Gemini: %s", exc)
        return UNAVAILABLE_MESSAGE


# ------------------------------------------------------------------------- Anthropic


def _run_anthropic(system, messages, tools, run_tool, max_iterations, max_tokens) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    conversation: list[dict] = [{"role": m["role"], "content": m["content"]} for m in messages]

    for _ in range(max_iterations):
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=conversation,
            tools=tools,
        )

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        conversation.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": run_tool(block.name, block.input)})

        conversation.append({"role": "user", "content": tool_results})

    return TOO_LONG_MESSAGE

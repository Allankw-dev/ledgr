"""Check your Gemini key and model BEFORE (or after) deploying.

    cd backend
    python -m scripts.dev.check_gemini

Reads GEMINI_API_KEY / GEMINI_MODEL from backend/.env, then:
  1. lists the Flash models your key can use,
  2. sends one tiny question through the same code the assistants use,
  3. does a tool-calling round trip (the assistants' real job).
Prints what to change if something is off. Never prints your key.
"""

import json

import httpx

from app.core.config import settings
from app.services import llm

if not settings.gemini_api_key:
    raise SystemExit("GEMINI_API_KEY is not set. Put it in backend/.env (get a free one at https://aistudio.google.com/apikey).")

print(f"Provider in use: {llm.active_provider()}   Configured model: {settings.gemini_model}")

r = httpx.get(f"{llm.GEMINI_BASE}/models", headers={"x-goog-api-key": settings.gemini_api_key}, params={"pageSize": 1000}, timeout=30)
if r.status_code != 200:
    raise SystemExit(f"Google rejected the key ({r.status_code}): {r.text[:300]}")
models = r.json().get("models", [])
flash = sorted(m["name"].removeprefix("models/") for m in models
               if "generateContent" in m.get("supportedGenerationMethods", []) and "flash" in m["name"])
print("Flash models available to this key:\n  " + "\n  ".join(flash))
print("Suggested if yours is retired:", llm._pick_replacement_model(models))

print("\n--- plain question ---")
print(llm.run_tool_conversation(system="Answer in one short sentence.", messages=[{"role": "user", "content": "What is 2+2?"}],
                                tools=[], run_tool=lambda n, i: "{}", max_iterations=2))

print("\n--- tool calling ---")
tools = [{"name": "get_balance", "description": "Returns the fee balance owed.", "input_schema": {"type": "object", "properties": {}}}]
print(llm.run_tool_conversation(system="Use the tool to answer. Be brief.", messages=[{"role": "user", "content": "How much is owed?"}],
                                tools=tools, run_tool=lambda n, i: json.dumps({"balance_kes": 12500}), max_iterations=3))
print("\nIf both answers look right, the AI assistants will work.")

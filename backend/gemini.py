"""Gemini service. The API key is read from the environment and never leaves the backend."""
import os
from .llm_prompts import SYSTEM


async def generate(history, message, context_json):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)
    contents = [types.Content(role="user" if h["role"] == "user" else "model",
                              parts=[types.Part.from_text(text=h["content"])]) for h in history[-6:]]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(
        text=f"USER QUESTION:\n{message}\n\nBACKEND DATA (authoritative JSON):\n{context_json}")]))
    resp = await client.aio.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), contents=contents,
        config=types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0.3, max_output_tokens=1000,
                                           thinking_config=types.ThinkingConfig(thinking_budget=0)))
    return (resp.text or "").strip() or None

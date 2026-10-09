"""Thin Groq (OpenAI-compatible) client with JSON mode, 429 backoff, and usage capture."""
import asyncio
import json
import time

import httpx

from .config import settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0))


class LLMError(Exception):
    pass


async def chat_json(model: str, messages: list[dict], temperature: float, max_tokens: int = 1500) -> tuple[dict, dict, int]:
    payload = {
        "model": model, "messages": messages, "temperature": temperature,
        "max_tokens": max_tokens, "response_format": {"type": "json_object"},
    }
    if "gpt-oss" in model:
        # Reasoning models: hidden reasoning tokens count against max_tokens.
        # Low effort keeps support-bot latency down; answers are grounded in retrieved text anyway.
        payload["reasoning_effort"] = "low"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    for attempt in range(4):
        t0 = time.perf_counter()
        try:
            r = await _client.post(GROQ_URL, json=payload, headers=headers)
        except httpx.TransportError as e:
            if attempt == 3:
                raise LLMError(f"transport: {e}") from e
            await asyncio.sleep(2 ** attempt); continue
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if r.status_code == 429 or r.status_code >= 500:
            wait = float(r.headers.get("retry-after", 2 ** attempt))
            await asyncio.sleep(min(wait, 20)); continue
        if r.status_code != 200:
            raise LLMError(f"{r.status_code}: {r.text[:300]}")
        body = r.json()
        try:
            parsed = json.loads(body["choices"][0]["message"]["content"])
        except (json.JSONDecodeError, KeyError) as e:
            raise LLMError("model returned non-JSON") from e
        return parsed, body.get("usage", {}), latency_ms
    raise LLMError("retries exhausted (rate limited)")

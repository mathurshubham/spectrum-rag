import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from .config import settings

_CF_BASE = "https://gateway.ai.cloudflare.com/v1"
_OPENROUTER_DIRECT = "https://openrouter.ai/api/v1/chat/completions"
_OPENAI_DIRECT = "https://api.openai.com/v1/chat/completions"
_TIMEOUT = 60.0


def _build_url(account_id: str, gateway_id: str) -> str:
    if account_id and gateway_id:
        return f"{_CF_BASE}/{account_id}/{gateway_id}/openrouter/v1/chat/completions"
    return _OPENROUTER_DIRECT


def _is_openai_reasoning(model: str) -> bool:
    # o-series reasoning models (o1/o3/o4-...) use max_completion_tokens and reject temperature.
    m = model.lower()
    return m.startswith("o1") or m.startswith("o3") or m.startswith("o4")


def _prepare_request(
    *,
    provider: str,
    messages: list[dict],
    model: str,
    openrouter_key: str,
    openai_key: str | None,
    account_id: str | None,
    gateway_id: str | None,
    max_tokens: int,
    temperature: float,
    stream: bool,
) -> tuple[str, dict, dict]:
    """Return (url, payload, headers) for the chosen provider."""
    payload: dict[str, Any] = {"model": model, "messages": messages}
    if stream:
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}

    if provider == "openai":
        url = _OPENAI_DIRECT
        if _is_openai_reasoning(model):
            payload["max_completion_tokens"] = max_tokens  # reasoning models: no temperature
        else:
            payload["max_tokens"] = max_tokens
            payload["temperature"] = temperature
        headers = {
            "Authorization": f"Bearer {openai_key}",
            "Content-Type": "application/json",
        }
    else:
        url = _build_url(
            account_id or settings.cf_account_id,
            gateway_id or settings.cf_gateway_id,
        )
        payload["max_tokens"] = max_tokens
        payload["temperature"] = temperature
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://rag-demos",
            "X-Title": "RAG Demos",
        }
    return url, payload, headers


async def chat_completion(
    messages: list[dict],
    model: str,
    openrouter_key: str,
    *,
    provider: str = "openrouter",
    openai_key: str | None = None,
    account_id: str | None = None,
    gateway_id: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.1,
) -> dict[str, Any]:
    url, payload, headers = _prepare_request(
        provider=provider, messages=messages, model=model,
        openrouter_key=openrouter_key, openai_key=openai_key,
        account_id=account_id, gateway_id=gateway_id,
        max_tokens=max_tokens, temperature=temperature, stream=False,
    )
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    # OpenRouter (esp. free tier) can return HTTP 200 with an error body and no
    # "choices" — surface it clearly instead of a raw KeyError → opaque 500.
    if "choices" not in data or not data["choices"]:
        err = (data.get("error") or {})
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise RuntimeError(f"model '{model}' returned no choices: {msg or data}")
    text = data["choices"][0]["message"].get("content") or ""
    usage = data.get("usage", {})
    return {
        "text": text,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }


async def chat_completion_stream(
    messages: list[dict],
    model: str,
    openrouter_key: str,
    *,
    provider: str = "openrouter",
    openai_key: str | None = None,
    account_id: str | None = None,
    gateway_id: str | None = None,
    max_tokens: int = 2500,
    temperature: float = 0.1,
) -> AsyncIterator[dict[str, Any]]:
    """Stream a chat completion. Yields {"type": "delta", "text": ...} for each
    content chunk, then a final {"type": "done", "usage": {...}}."""
    url, payload, headers = _prepare_request(
        provider=provider, messages=messages, model=model,
        openrouter_key=openrouter_key, openai_key=openai_key,
        account_id=account_id, gateway_id=gateway_id,
        max_tokens=max_tokens, temperature=temperature, stream=True,
    )
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        async with client.stream("POST", url, json=payload, headers=headers) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    chunk = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                if chunk.get("usage"):
                    u = chunk["usage"]
                    usage = {
                        "prompt_tokens": u.get("prompt_tokens", 0),
                        "completion_tokens": u.get("completion_tokens", 0),
                        "total_tokens": u.get("total_tokens", 0),
                    }
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    text = delta.get("content")
                    if text:
                        yield {"type": "delta", "text": text}
    yield {"type": "done", "usage": usage}

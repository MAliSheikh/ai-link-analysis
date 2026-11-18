"""LLM (Large Language Model) clients for Gemini, Anthropic Claude and OpenAI.

We call each provider's REST (Representational State Transfer) API directly with HTTPX,
so there is one simple code path and no heavy SDK (Software Development Kit).
Features: JSON mode, retry on temporary errors, and an optional fallback provider.
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.config import settings
from app.utils.validators import AppError

logger = logging.getLogger(__name__)


class LLMConfigError(AppError):
    code = "llm_not_configured"


class LLMServiceError(AppError):
    status_code = 502
    code = "llm_error"


class RetryableLLMError(LLMServiceError):
    """Temporary problem (timeout, rate limit, server error). Safe to try again."""


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_seconds: float


def extract_json(text: str) -> dict:
    """Get a JSON object from the model text, even if it is wrapped in ```json fences."""
    cleaned = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.S)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No JSON object found in the model answer.")
        data = json.loads(cleaned[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("Model answer is JSON but not an object.")
    return data


def _raise_for_status(provider: str, resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    detail = resp.text[:300]
    if resp.status_code in (408, 429) or resp.status_code >= 500:
        raise RetryableLLMError(f"{provider} temporary error {resp.status_code}: {detail}")
    raise LLMServiceError(f"{provider} request failed ({resp.status_code}): {detail}")


class BaseLLMClient:
    provider = "base"

    def __init__(self, model: str, api_key: str):
        self.model = model
        self.api_key = api_key

    async def _post(self, url: str, headers: dict, payload: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise RetryableLLMError(f"{self.provider} took too long to answer (timeout).")
        except httpx.HTTPError as exc:
            raise RetryableLLMError(f"Could not reach {self.provider}: {exc.__class__.__name__}")
        _raise_for_status(self.provider, resp)
        return resp.json()

    async def generate_json(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        raise NotImplementedError


class GeminiClient(BaseLLMClient):
    provider = "gemini"

    async def generate_json(self, system, user, max_tokens):
        url = settings.api_url_for(self.provider, self.model)
        config = {"responseMimeType": "application/json", "temperature": 0.3,
                  "maxOutputTokens": max_tokens}
        if settings.GEMINI_THINKING_BUDGET != "" and "2.5" in self.model:
            config["thinkingConfig"] = {"thinkingBudget": int(settings.GEMINI_THINKING_BUDGET)}
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": config,
        }
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        start = time.perf_counter()
        data = await self._post(url, headers, payload)
        latency = time.perf_counter() - start

        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMServiceError("Gemini returned no answer (it may be blocked by safety filters).")
        if candidates[0].get("finishReason") == "MAX_TOKENS":
            raise LLMServiceError("Gemini answer was cut off (max output tokens reached).")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        usage = data.get("usageMetadata", {})
        out_tokens = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
        return LLMResponse(text, self.provider, self.model, usage.get("promptTokenCount", 0),
                           out_tokens, latency)


class AnthropicClient(BaseLLMClient):
    provider = "anthropic"

    async def generate_json(self, system, user, max_tokens):
        payload = {"model": self.model, "max_tokens": max_tokens, "system": system,
                   "messages": [{"role": "user", "content": user}]}
        headers = {"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        start = time.perf_counter()
        data = await self._post(settings.api_url_for(self.provider, self.model), headers, payload)
        latency = time.perf_counter() - start

        if data.get("stop_reason") == "max_tokens":
            raise LLMServiceError("Claude answer was cut off (max output tokens reached).")
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return LLMResponse(text, self.provider, self.model, usage.get("input_tokens", 0),
                           usage.get("output_tokens", 0), latency)


class OpenAIClient(BaseLLMClient):
    provider = "openai"

    async def generate_json(self, system, user, max_tokens):
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_object"},
            # reasoning models count hidden reasoning tokens here too, so give more room
            "max_completion_tokens": max_tokens * 2,
        }
        if settings.OPENAI_REASONING_EFFORT:
            payload["reasoning_effort"] = settings.OPENAI_REASONING_EFFORT
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        start = time.perf_counter()
        data = await self._post(settings.api_url_for(self.provider, self.model), headers, payload)
        latency = time.perf_counter() - start

        choice = (data.get("choices") or [{}])[0]
        if choice.get("finish_reason") == "length":
            raise LLMServiceError("OpenAI answer was cut off (max output tokens reached).")
        text = (choice.get("message") or {}).get("content") or ""
        usage = data.get("usage", {})
        return LLMResponse(text, self.provider, self.model, usage.get("prompt_tokens", 0),
                           usage.get("completion_tokens", 0), latency)


CLIENTS = {"gemini": GeminiClient, "anthropic": AnthropicClient, "openai": OpenAIClient}


def build_client(provider: str, model: str) -> BaseLLMClient:
    if provider not in CLIENTS:
        raise LLMConfigError(f"Unknown LLM_PROVIDER '{provider}'. Use: gemini, anthropic or openai.")
    if not settings.api_url_for(provider, model):
        raise LLMConfigError(f"API URL for '{provider}' is missing or invalid. Add it to your .env file.")
    key = settings.api_key_for(provider)
    if not key:
        raise LLMConfigError(f"API key for '{provider}' is missing. Add it to your .env file.")
    return CLIENTS[provider](model, key)


class LLMService:
    """Tries the main model (2 attempts), then the fallback model if one is set."""

    def __init__(self, clients: List[BaseLLMClient], max_tokens: int = 8000):
        self.clients = clients
        self.max_tokens = max_tokens

    @classmethod
    def from_settings(cls) -> "LLMService":
        clients = [build_client(settings.LLM_PROVIDER, settings.LLM_MODEL)]
        if settings.LLM_FALLBACK_PROVIDER:
            try:
                clients.append(build_client(settings.LLM_FALLBACK_PROVIDER, settings.LLM_FALLBACK_MODEL))
            except LLMConfigError as exc:
                logger.warning("Fallback LLM disabled: %s", exc.message)
        return cls(clients, settings.MAX_OUTPUT_TOKENS)

    async def generate(self, system: str, user: str) -> LLMResponse:
        errors = []
        for client in self.clients:
            for attempt in range(2):
                try:
                    return await client.generate_json(system, user, self.max_tokens)
                except RetryableLLMError as exc:
                    errors.append(exc.message)
                    logger.warning("%s attempt %d failed: %s", client.provider, attempt + 1, exc.message)
                    await asyncio.sleep(1.5 * (attempt + 1))
                except LLMServiceError as exc:  # not temporary -> go to fallback
                    errors.append(exc.message)
                    logger.warning("%s failed: %s", client.provider, exc.message)
                    break
        raise LLMServiceError("AI (Artificial Intelligence) analysis failed. " + " | ".join(errors[-2:]))

"""App settings. All secrets come from environment variables (.env file)."""
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODELS = {
    "gemini": "gemini-3.8-flash",
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-5.4-mini",
}

# Standard paid list prices in USD per 1 million tokens, checked 18 Nov 2026.
MODEL_PRICES_PER_MILLION = {
    "gemini-3.8-flash": {"input": 0.75, "output": 3.75},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-lite": {"input": 0.10, "output": 0.40},
    # Haiku 5.5 price goes up 5x when one prompt is over 100K tokens.
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50,
                         "long_input": 0.50, "long_output": 2.50, "long_threshold": 100_000},
    "gpt-5.4-mini": {"input": 0.75, "output": 4.50},
    "gpt-5-mini": {"input": 0.25, "output": 2.00},
}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        self.LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
        self.LLM_MODEL = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS.get(self.LLM_PROVIDER, "")
        self.LLM_FALLBACK_PROVIDER = os.getenv("LLM_FALLBACK_PROVIDER", "").strip().lower()
        self.LLM_FALLBACK_MODEL = (os.getenv("LLM_FALLBACK_MODEL", "").strip()
                                   or DEFAULT_MODELS.get(self.LLM_FALLBACK_PROVIDER, ""))

        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self.GEMINI_API_URL_TEMPLATE = os.getenv("GEMINI_API_URL_TEMPLATE", "").strip()
        self.ANTHROPIC_API_URL = os.getenv("ANTHROPIC_API_URL", "").strip()
        self.OPENAI_API_URL = os.getenv("OPENAI_API_URL", "").strip()

        # "0" turns off Gemini 2.5 Flash "thinking" -> faster and cheaper. Empty = model default.
        self.GEMINI_THINKING_BUDGET = os.getenv("GEMINI_THINKING_BUDGET", "0").strip()
        self.OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "").strip()

        self.FETCH_TIMEOUT_SECONDS = _float("FETCH_TIMEOUT_SECONDS", 15.0)
        self.JS_RENDER_TIMEOUT_SECONDS = _float("JS_RENDER_TIMEOUT_SECONDS", 20.0)
        default_js_render = "false" if os.getenv("VERCEL") == "1" else "true"
        self.JS_RENDER_ENABLED = os.getenv("JS_RENDER_ENABLED", default_js_render).strip().lower() in {
            "1", "true", "yes", "on"
        }
        self.LLM_TIMEOUT_SECONDS = _float("LLM_TIMEOUT_SECONDS", 90.0)
        self.MAX_PAGE_BYTES = _int("MAX_PAGE_BYTES", 3_000_000)
        self.MAX_REDIRECTS = _int("MAX_REDIRECTS", 5)
        self.MAX_CONTENT_CHARS = _int("MAX_CONTENT_CHARS", 12_000)
        self.MAX_EXTRA_PAGES = _int("MAX_EXTRA_PAGES", 2)
        self.MAX_OUTPUT_TOKENS = _int("MAX_OUTPUT_TOKENS", 8_000)
        self.CACHE_TTL_SECONDS = _int("CACHE_TTL_SECONDS", 3600)

    def api_key_for(self, provider: str) -> str:
        return {
            "gemini": self.GEMINI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "openai": self.OPENAI_API_KEY,
        }.get(provider, "")

    def api_url_for(self, provider: str, model: str) -> str:
        if provider == "gemini":
            template = self.GEMINI_API_URL_TEMPLATE
            if "{model}" not in template:
                return ""
            return template.replace("{model}", model)
        return {
            "anthropic": self.ANTHROPIC_API_URL,
            "openai": self.OPENAI_API_URL,
        }.get(provider, "")


settings = Settings()


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Estimated cost of ONE LLM call, from public list prices. None if model is unknown."""
    price = MODEL_PRICES_PER_MILLION.get(model)
    if not price:
        return None
    in_rate, out_rate = price["input"], price["output"]
    if "long_threshold" in price and input_tokens > price["long_threshold"]:
        in_rate, out_rate = price["long_input"], price["long_output"]
    return round((input_tokens * in_rate + output_tokens * out_rate) / 1_000_000, 6)

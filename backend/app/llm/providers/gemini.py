# app/llm/providers/gemini.py
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx
from google import genai
from google.genai import types

from app.core.config import settings
from app.llm.errors import LLMRetryableError, LLMNonRetryableError
from app.llm.types import LLMRequest, LLMResponse


@dataclass
class GeminiProvider:
    """
    Gemini provider using Google Gen AI SDK (google-genai).
    Single-attempt. Retries/backoff handled by app/llm/client.py.
    """
    _client: Optional[genai.Client] = None

    def _get_client(self) -> genai.Client:
        if not settings.GEMINI_API_KEY:
            raise LLMNonRetryableError("GEMINI_API_KEY is missing")
        if self._client is None:
            # Keep client simple; per-call timeout goes via GenerateContentConfig.http_options
            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        return self._client

    def generate(self, req: LLMRequest, prompt: str) -> LLMResponse:
        client = self._get_client()
        start_ms = int(time.time() * 1000)

        try:
            # NOTE: timeout in this SDK is typically milliseconds in HttpOptions (repo examples).
            # We'll convert seconds -> ms.
            http_opts = types.HttpOptions(timeout=int(req.timeout_seconds * 1000))

            cfg = types.GenerateContentConfig(
                temperature=req.temperature,
                max_output_tokens=req.max_output_tokens,
                response_mime_type=req.response_mime_type,
                http_options=http_opts,
            )

            resp = client.models.generate_content(
                model=req.model,
                contents=prompt,
                config=cfg,
            )

            text = (getattr(resp, "text", None) or "").strip()

            # Token usage: best-effort, won't break if missing
            input_tokens = None
            output_tokens = None
            usage = getattr(resp, "usage_metadata", None)
            if usage is not None:
                input_tokens = getattr(usage, "prompt_token_count", None)
                output_tokens = getattr(usage, "candidates_token_count", None)

            latency_ms = int(time.time() * 1000) - start_ms

            return LLMResponse(
                trace_id=req.trace_id,
                provider=req.provider,
                model=req.model,
                output_text=text,
                latency_ms=latency_ms,
                retries=0,
                raw={"sdk_response_type": str(type(resp))},
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        # ---- classify retryable failures first (so client.py retries) ----
        except (httpx.TimeoutException, TimeoutError) as e:
            raise LLMRetryableError(f"Gemini call timed out: {e}") from e
        except httpx.HTTPError as e:
            raise LLMRetryableError(f"Gemini http error (retryable): {e}") from e
        except Exception as e:
            msg = str(e).lower()
            if any(x in msg for x in ["429", "rate", "quota", "500", "503", "temporarily"]):
                raise LLMRetryableError(f"Gemini retryable failure: {e}") from e
            raise LLMNonRetryableError(f"Gemini non-retryable failure: {e}") from e

# app/llm/client.py


import uuid
import time
import json
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.llm.errors import LLMNonRetryableError, LLMRetryableError
from app.llm.prompts.registry import get_prompt
from app.llm.telemetry import LLMCallLog, log_llm_call, now_ms
from app.llm.types import LLMRequest, LLMResponse
from app.llm.providers.gemini import GeminiProvider

T = TypeVar("T", bound=BaseModel)


def _render_template(template: str, variables: dict) -> str:
    out = template
    for k, v in variables.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def llm_generate(
    *,
    purpose: str,
    prompt_name: str,
    prompt_version: str,
    variables: dict,
    response_mime_type: str | None = "application/json",
) -> LLMResponse:
    trace_id = str(uuid.uuid4())

    if settings.LLM_PROVIDER != "gemini":
        raise LLMNonRetryableError(f"Unsupported provider: {settings.LLM_PROVIDER}")

    # Ensure repair placeholder exists and is empty by default
    safe_vars = dict(variables)
    safe_vars.setdefault("__REPAIR_INSTRUCTIONS__", "")

    # Adjust max tokens for specific purposes
    max_tokens = settings.LLM_MAX_OUTPUT_TOKENS
    if purpose == "parse_matrix":
        max_tokens = max(max_tokens, 8192)


    req = LLMRequest(
        trace_id=trace_id,
        purpose=purpose,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        variables=safe_vars,
        provider="gemini",
        model=settings.GEMINI_MODEL,
        temperature=settings.LLM_TEMPERATURE,
        max_output_tokens=max_tokens,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        response_mime_type=response_mime_type,
    )

    tmpl = get_prompt(prompt_name, prompt_version)
    rendered = _render_template(tmpl.template, safe_vars)

    client = GeminiProvider()

    start_ms = now_ms()
    retries = 0
    last_err: Exception | None = None

    for attempt in range(settings.LLM_MAX_RETRIES + 1):
        try:
            resp = client.generate(req, rendered)

            log_llm_call(
                LLMCallLog(
                    trace_id=trace_id,
                    provider=req.provider,
                    model=req.model,
                    purpose=purpose,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    latency_ms=(now_ms() - start_ms),
                    retries=retries,
                    ok=True,
                )
            )

            return LLMResponse(
                trace_id=resp.trace_id,
                provider=resp.provider,
                model=resp.model,
                output_text=resp.output_text,
                latency_ms=resp.latency_ms,
                retries=retries,
                raw=resp.raw,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
            )

        except LLMRetryableError as e:
            last_err = e
            retries += 1

            if attempt >= settings.LLM_MAX_RETRIES:
                break

            time.sleep(min(2.0, 0.25 * (2 ** attempt)))

        except LLMNonRetryableError as e:
            log_llm_call(
                LLMCallLog(
                    trace_id=trace_id,
                    provider=req.provider,
                    model=req.model,
                    purpose=purpose,
                    prompt_name=prompt_name,
                    prompt_version=prompt_version,
                    latency_ms=(now_ms() - start_ms),
                    retries=retries,
                    ok=False,
                    error_type=type(e).__name__,
                )
            )
            raise

    log_llm_call(
        LLMCallLog(
            trace_id=trace_id,
            provider=req.provider,
            model=req.model,
            purpose=purpose,
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            latency_ms=(now_ms() - start_ms),
            retries=retries,
            ok=False,
            error_type=type(last_err).__name__ if last_err else "LLMError",
        )
    )
    raise last_err if last_err else LLMRetryableError("LLM failed after retries")


def llm_generate_structured(
    *,
    purpose: str,
    prompt_name: str,
    prompt_version: str,
    variables: dict,
    schema: Type[T],
) -> T:
    resp = llm_generate(
        purpose=purpose,
        prompt_name=prompt_name,
        prompt_version=prompt_version,
        variables=variables,
        response_mime_type="application/json",
    )

    try:
        data = json.loads(resp.output_text)
        return schema.model_validate(data)
    except (json.JSONDecodeError, ValidationError):
        repaired_vars = dict(variables)
        repaired_vars["__REPAIR_INSTRUCTIONS__"] = (
            "You MUST return valid JSON only. "
            "Escape all quotes and newlines inside strings. "
            "Do not include any raw line breaks inside string values. "
            "No markdown. No trailing commas. "
            "Return EXACTLY the schema with correct types."
        )

        resp2 = llm_generate(
            purpose=purpose + "_repair",
            prompt_name=prompt_name,
            prompt_version=prompt_version,
            variables=repaired_vars,
            response_mime_type="application/json",
        )

        data2 = json.loads(resp2.output_text)
        return schema.model_validate(data2)

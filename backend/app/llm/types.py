# app/llm/types.py
from dataclasses import dataclass
from typing import Any, Literal

JsonDict = dict[str, Any]

@dataclass(frozen=True)
class LLMRequest:
    trace_id: str
    purpose: str                    # e.g. "parse_matrix", "generate_examples"
    prompt_name: str                # registry key
    prompt_version: str             # e.g. "v1"
    variables: JsonDict             # variables for prompt template

    provider: str                   # "gemini"
    model: str                      # e.g. "gemini-1.5-pro"

    temperature: float
    max_output_tokens: int
    timeout_seconds: int

    # If you want strict JSON outputs for certain calls
    response_mime_type: str | None = None  # e.g. "application/json"

@dataclass(frozen=True)
class LLMResponse:
    trace_id: str
    provider: str
    model: str
    output_text: str

    # Optional metadata (provider-dependent)
    latency_ms: int
    retries: int
    raw: JsonDict | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

LLMStatus = Literal["ok", "error"]

# app/llm/telemetry.py

import logging
import time
from dataclasses import dataclass

logger = logging.getLogger("llm")

@dataclass
class LLMCallLog:
    trace_id: str
    provider: str
    model: str
    purpose: str
    prompt_name: str
    prompt_version: str
    latency_ms: int
    retries: int
    ok: bool
    error_type: str | None = None

def now_ms() -> int:
    return int(time.time() * 1000)

def log_llm_call(item: LLMCallLog) -> None:
    logger.info(
        "llm_call trace_id=%s provider=%s model=%s purpose=%s prompt=%s@%s latency_ms=%s retries=%s ok=%s error=%s",
        item.trace_id,
        item.provider,
        item.model,
        item.purpose,
        item.prompt_name,
        item.prompt_version,
        item.latency_ms,
        item.retries,
        item.ok,
        item.error_type,
    )

# app/llm/errors.py
class LLMError(Exception):
    """Base LLM error (wrapped)."""

class LLMRetryableError(LLMError):
    """Transient error: timeouts, 429s, 5xx, network."""

class LLMNonRetryableError(LLMError):
    """Bad request, auth, prompt too large, schema mismatch."""

"""
guide_validators.py
- Purpose: Validations specific to leveling guide domain inputs.
- Design: Normalize + validate at the boundary, keep services clean.
"""

from urllib.parse import urlparse
from app.core import AppError, ErrorCode, ErrorReason
from app.core.error_codes import ErrorCode


def validate_role_title(role_title: str) -> None:
    rt = (role_title or "").strip()
    if len(rt) < 3 or len(rt) > 120:
        raise AppError(code=ErrorCode.GUIDE_INVALID_ROLE_TITLE, status_code=422)


def normalize_website_url(url: str) -> str:
    """
    Normalize URL to reduce duplicates:
    - enforce http/https
    - lowercase host
    - remove trailing slash
    """
    u = (url or "").strip()
    parsed = urlparse(u)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise AppError(code=ErrorCode.GUIDE_INVALID_URL, status_code=422)

    return f"{parsed.scheme}://{parsed.netloc.lower()}".rstrip("/")

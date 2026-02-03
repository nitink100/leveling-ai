"""
Request/Task context helpers.

We keep a small context (request_id, task_id, guide_id, etc.) in ContextVars.
Both FastAPI middleware and Celery tasks can set these values so logs become
correlatable across the pipeline.

No external dependencies.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Dict, Optional


_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_task_id: ContextVar[Optional[str]] = ContextVar("task_id", default=None)
_guide_id: ContextVar[Optional[str]] = ContextVar("guide_id", default=None)
_role_title: ContextVar[Optional[str]] = ContextVar("role_title", default=None)


def set_context(
    *,
    request_id: Optional[str] = None,
    task_id: Optional[str] = None,
    guide_id: Optional[str] = None,
    role_title: Optional[str] = None,
) -> None:
    if request_id is not None:
        _request_id.set(request_id)
    if task_id is not None:
        _task_id.set(task_id)
    if guide_id is not None:
        _guide_id.set(guide_id)
    if role_title is not None:
        _role_title.set(role_title)


def clear_context() -> None:
    _request_id.set(None)
    _task_id.set(None)
    _guide_id.set(None)
    _role_title.set(None)


def get_context() -> Dict[str, Any]:
    ctx: Dict[str, Any] = {}
    rid = _request_id.get()
    tid = _task_id.get()
    gid = _guide_id.get()
    role = _role_title.get()

    if rid:
        ctx["request_id"] = rid
    if tid:
        ctx["task_id"] = tid
    if gid:
        ctx["guide_id"] = gid
    if role:
        ctx["role_title"] = role
    return ctx

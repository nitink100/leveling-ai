"""
statuses.py
- Purpose: Central source of truth for pipeline statuses.
- Design: Keep FE-facing statuses stable and explicit.
"""

from enum import Enum


class GuideStatus(str, Enum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    RUNNING_EXTRACT = "RUNNING_EXTRACT"
    RUNNING_PARSE = "RUNNING_PARSE"
    RUNNING_GENERATE = "RUNNING_GENERATE"
    READY = "READY"
    FAILED = "FAILED"

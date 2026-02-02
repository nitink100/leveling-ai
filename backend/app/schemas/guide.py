"""
guide.py (schemas)
- Purpose: Request/response DTOs for the leveling guide domain.
- Design: Keep API DTOs stable; include helper constructors for DRY mapping.
"""

from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Literal
from uuid import UUID
from datetime import datetime

from app.constants.statuses import GuideStatus


class LevelingGuideCreateRequest(BaseModel):
    """
    Internal DTO. Router will build this if needed later.
    For now service accepts raw fields (website_url, role_title, pdf).
    """
    website_url: HttpUrl
    role_title: str = Field(min_length=3, max_length=120)


class LevelingGuideCreateResponse(BaseModel):
    """
    API response after upload. Keeps frontend integration simple.
    """
    guide_id: UUID
    company_id: UUID
    status: Literal[
        "UPLOADED", "QUEUED", "RUNNING_EXTRACT", "RUNNING_PARSE", "RUNNING_GENERATE", "READY", "FAILED"
    ]
    status_url: str
    results_url: str
    pdf_url: str
    created_at: datetime

    @classmethod
    def from_guide(cls, guide) -> "LevelingGuideCreateResponse":
        """
        DRY mapper from ORM model -> response DTO.
        """
        gid = guide.id
        return cls(
            guide_id=gid,
            company_id=guide.company_id,
            status=str(guide.status),
            status_url=f"/api/guides/{gid}/status",
            results_url=f"/api/guides/{gid}/results",
            pdf_url=f"/api/guides/{gid}/pdf",
            created_at=guide.created_at,
        )

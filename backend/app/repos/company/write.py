"""
company/write.py
- Purpose: Write-side DB operations for Company.
- Design: No business logic. Only persistence and minimal mapping.
"""

from sqlalchemy.orm import Session
from app.models.company import Company


class CompanyWriteRepo:
    def __init__(self, db: Session):
        self.db = db

    def upsert_by_website(
        self,
        website_url: str,
        *,
        company_name: str | None = None,
        company_context: str | None = None,
    ) -> Company:
        existing = self.db.query(Company).filter(Company.website_url == website_url).first()
        if existing:
            #update if provided
            if company_name and company_name.strip():
                existing.name = company_name.strip()

            if company_context and company_context.strip():
                existing.context = company_context.strip()

            self.db.commit()
            self.db.refresh(existing)
            return existing

        company = Company(
            website_url=website_url,
            name=company_name.strip() if company_name and company_name.strip() else None,
            context=company_context.strip() if company_context and company_context.strip() else None,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

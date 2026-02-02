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

    def upsert_by_website(self, website_url: str) -> Company:
        """
        For prototype:
        - A "company" is uniquely identified by website_url.
        - If found, return it; else create.
        """
        existing = self.db.query(Company).filter(Company.website_url == website_url).first()
        if existing:
            return existing

        company = Company(website_url=website_url)
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

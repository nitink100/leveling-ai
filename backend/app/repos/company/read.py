"""
company/read.py
- Purpose: Read-side DB operations for Company.
- Design: Keep query logic here for reuse and testability.
"""

from sqlalchemy.orm import Session
from app.models.company import Company


class CompanyReadRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, company_id):
        return self.db.query(Company).filter(Company.id == company_id).first()

    def get_by_website(self, website_url: str):
        return self.db.query(Company).filter(Company.website_url == website_url).first()

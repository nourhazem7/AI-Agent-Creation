from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.company import Company


def create_company(db: Session, name: str) -> Company:
    company = Company(name=name)
    db.add(company)
    db.flush()
    return company


def get_company(db: Session, company_id: str) -> Company | None:
    return db.get(Company, company_id)

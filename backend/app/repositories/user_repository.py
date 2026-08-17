from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def create_user(
    db: Session,
    *,
    company_id: str,
    email: str,
    hashed_password: str,
    full_name: str | None = None,
    role: str = "admin",
) -> User:
    user = User(
        company_id=company_id,
        email=email.lower(),
        hashed_password=hashed_password,
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower())
    return db.execute(stmt).scalar_one_or_none()


def get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def list_active_users_for_company(db: Session, company_id: str) -> list[User]:
    stmt = (
        select(User)
        .where(User.company_id == company_id, User.is_active.is_(True))
        .order_by(User.full_name, User.email)
    )
    return list(db.execute(stmt).scalars().all())

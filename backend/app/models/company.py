from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import IdTimestampMixin


class Company(IdTimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    agents: Mapped[list["Agent"]] = relationship(back_populates="company", cascade="all, delete-orphan")

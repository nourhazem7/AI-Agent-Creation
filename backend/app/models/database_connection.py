from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import IdTimestampMixin

# Only dialects with a driver actually installed (see backend/requirements.txt) are
# ever written here. The frontend must not offer dialects outside this set as connectable.
SUPPORTED_DIALECTS = ("postgresql", "mysql", "sqlite", "mssql")


class DatabaseConnection(IdTimestampMixin, Base):
    __tablename__ = "database_connections"

    agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id"), nullable=False, unique=True, index=True
    )

    dialect: Mapped[str] = mapped_column(String(50), nullable=False)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    database_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Never null for postgresql/mysql/mssql; unused for sqlite. Fernet ciphertext.
    encrypted_password: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Only used when dialect == "sqlite" — a path under backend/storage or a path the user typed.
    sqlite_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # JSON-encoded dict of dialect-specific extras (e.g. {"sslmode": "require"}).
    extra_params: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    last_tested_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped["Agent"] = relationship(back_populates="database_connection")

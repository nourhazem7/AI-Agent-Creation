from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.database_connection import SUPPORTED_DIALECTS


class ConnectionFields(BaseModel):
    dialect: str = Field(description=f"One of: {', '.join(SUPPORTED_DIALECTS)}")
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    password: str | None = None
    sqlite_file_path: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "ConnectionFields":
        if self.dialect not in SUPPORTED_DIALECTS:
            raise ValueError(f"Unsupported dialect '{self.dialect}'. Supported: {', '.join(SUPPORTED_DIALECTS)}")
        if self.dialect == "sqlite":
            if not self.sqlite_file_path:
                raise ValueError("sqlite_file_path is required for the sqlite dialect")
        elif not self.host or not self.database_name:
            raise ValueError("host and database_name are required for this dialect")
        return self


class ConnectionTestRequest(ConnectionFields):
    pass


class ConnectionCreateRequest(ConnectionFields):
    pass


class ConnectionTestResponse(BaseModel):
    ok: bool
    error: str | None = None


class ConnectionSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dialect: str
    host: str | None
    port: int | None
    database_name: str | None
    username: str | None
    sqlite_file_path: str | None
    is_connected: bool
    last_tested_at: datetime | None

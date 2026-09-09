import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    employee = "employee"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'manager', 'employee')", name="ck_users_role"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    role: Mapped[str] = mapped_column(
        String(20), default=UserRole.employee.value, server_default=UserRole.employee.value
    )
    departments: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def allowed_roles(self) -> list[str]:
        roles = {self.role, "all"}
        roles.update(self.departments or [])
        return sorted(roles)

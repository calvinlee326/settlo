import secrets
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import generate_uuid


def generate_invite_token() -> str:
    return secrets.token_urlsafe(16)


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_token: Mapped[str] = mapped_column(
        String(64), unique=True, default=generate_invite_token
    )
    max_members: Mapped[int] = mapped_column(Integer, default=20)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "group_id", name="uq_user_group"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    group: Mapped["Group"] = relationship(back_populates="memberships")
    user = relationship("User")

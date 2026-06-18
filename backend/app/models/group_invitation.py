import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import generate_uuid, utcnow


class GroupInvitationStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class GroupInvitation(Base):
    __tablename__ = "group_invitations"
    __table_args__ = (
        UniqueConstraint("group_id", "invited_user_id", name="uq_group_invitation"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    invited_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    invited_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    status: Mapped[GroupInvitationStatus] = mapped_column(
        Enum(GroupInvitationStatus, name="groupinvitationstatus"),
        default=GroupInvitationStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

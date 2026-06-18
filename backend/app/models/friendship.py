import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import generate_uuid, utcnow


class FriendshipStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    requester_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    addressee_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, name="friendshipstatus"),
        default=FriendshipStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

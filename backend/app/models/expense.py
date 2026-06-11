import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import generate_uuid


class SplitType(str, enum.Enum):
    EQUAL = "EQUAL"
    CUSTOM = "CUSTOM"


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    paid_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    split_type: Mapped[SplitType] = mapped_column(
        Enum(SplitType, name="splittype"), default=SplitType.EQUAL
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))

    splits: Mapped[list["ExpenseSplit"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )
    payer = relationship("User", foreign_keys=[paid_by])


class ExpenseSplit(Base):
    __tablename__ = "expense_splits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    expense_id: Mapped[str] = mapped_column(String(36), ForeignKey("expenses.id"))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    expense: Mapped["Expense"] = relationship(back_populates="splits")
    user = relationship("User")


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    from_user: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    to_user: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    from_user_obj = relationship("User", foreign_keys=[from_user])
    to_user_obj = relationship("User", foreign_keys=[to_user])

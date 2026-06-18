from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.expense import SplitType
from app.schemas.expense import SplitInput


class FriendRequestCreate(BaseModel):
    phone_number: str = Field(min_length=3, max_length=20)


class FriendRequestOut(BaseModel):
    id: str
    requester_id: str
    requester_username: str | None
    created_at: datetime


class FriendOut(BaseModel):
    id: str
    username: str | None
    phone_number: str
    net_balance: float


class DirectExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    paid_by: str
    split_type: SplitType = SplitType.EQUAL
    participant_ids: list[str] = Field(min_length=2)
    splits: list[SplitInput] | None = None

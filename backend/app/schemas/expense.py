from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.expense import SplitType


class SplitInput(BaseModel):
    user_id: str
    amount: Decimal = Field(ge=0, decimal_places=2)


class ExpenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    paid_by: str
    split_type: SplitType = SplitType.EQUAL
    splits: list[SplitInput] | None = None


class SplitOut(BaseModel):
    user_id: str
    username: str | None
    amount: float


class ExpenseOut(BaseModel):
    id: str
    group_id: str
    title: str
    amount: float
    currency: str
    split_type: SplitType
    paid_by: str
    paid_by_username: str | None
    created_by: str
    created_at: datetime
    splits: list[SplitOut] = []

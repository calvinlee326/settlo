from datetime import datetime

from pydantic import BaseModel


class SettlementOut(BaseModel):
    id: str
    group_id: str | None
    from_user: str
    from_username: str | None
    to_user: str
    to_username: str | None
    amount: float
    is_paid: bool
    paid_at: datetime | None
    created_at: datetime
    recorded_by: str | None = None
    recorded_by_username: str | None = None
    reversed_by: str | None = None
    reversed_by_username: str | None = None
    reversed_at: datetime | None = None


class BalanceOut(BaseModel):
    user_id: str
    username: str | None
    balance: float


class SettlementResult(BaseModel):
    balances: list[BalanceOut]
    settlements: list[SettlementOut]
    paid_settlements: list[SettlementOut] = []
    reversed_settlements: list[SettlementOut] = []

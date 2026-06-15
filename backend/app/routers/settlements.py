from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.group import Group, Membership
from app.models.user import User
from app.routers.groups import get_group_or_404, require_membership
from app.schemas.settlement import BalanceOut, SettlementOut, SettlementResult
from app.services.settlement import calculate_settlements

router = APIRouter(prefix="/api/groups/{group_id}/settlements", tags=["settlements"])

CENT = Decimal("0.01")
DRAFT_SETTLEMENT_PREFIX = "draft_"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _settlement_out(s: Settlement, usernames: dict[str, str | None]) -> SettlementOut:
    return SettlementOut(
        id=s.id,
        group_id=s.group_id,
        from_user=s.from_user,
        from_username=usernames.get(s.from_user),
        to_user=s.to_user,
        to_username=usernames.get(s.to_user),
        amount=float(s.amount),
        is_paid=s.is_paid,
        paid_at=s.paid_at,
        created_at=s.created_at,
    )


def _draft_settlement_id(
    group_id: str, from_user: str, to_user: str, amount: Decimal
) -> str:
    amount_key = str(amount.quantize(CENT))
    digest = sha256(f"{group_id}:{from_user}:{to_user}:{amount_key}".encode()).hexdigest()
    return f"{DRAFT_SETTLEMENT_PREFIX}{digest[:32]}"


def _transaction_out(
    group_id: str, transaction: dict, usernames: dict[str, str | None]
) -> SettlementOut:
    return SettlementOut(
        id=_draft_settlement_id(
            group_id,
            transaction["from_user"],
            transaction["to_user"],
            transaction["amount"],
        ),
        group_id=group_id,
        from_user=transaction["from_user"],
        from_username=usernames.get(transaction["from_user"]),
        to_user=transaction["to_user"],
        to_username=usernames.get(transaction["to_user"]),
        amount=float(transaction["amount"]),
        is_paid=False,
        paid_at=None,
        created_at=_utcnow(),
    )


def _compute_balances(db: Session, group_id: str) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    memberships = db.query(Membership).filter(Membership.group_id == group_id).all()
    for m in memberships:
        balances[m.user_id] = Decimal("0")

    expenses = db.query(Expense).filter(Expense.group_id == group_id).all()
    expense_ids = [e.id for e in expenses]
    for e in expenses:
        balances[e.paid_by] += Decimal(e.amount)
    if expense_ids:
        splits = (
            db.query(ExpenseSplit)
            .filter(ExpenseSplit.expense_id.in_(expense_ids))
            .all()
        )
        for s in splits:
            balances[s.user_id] -= Decimal(s.amount)

    # Completed settlements reduce outstanding debt
    paid = (
        db.query(Settlement)
        .filter(Settlement.group_id == group_id, Settlement.is_paid.is_(True))
        .all()
    )
    for s in paid:
        balances[s.from_user] += Decimal(s.amount)
        balances[s.to_user] -= Decimal(s.amount)

    return dict(balances)


@router.get("/", response_model=SettlementResult)
def get_settlements(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)

    balances = _compute_balances(db, group_id)
    transactions = calculate_settlements(balances)

    paid_settlements = (
        db.query(Settlement)
        .filter(Settlement.group_id == group_id, Settlement.is_paid.is_(True))
        .order_by(Settlement.paid_at.desc())
        .all()
    )

    user_ids = set(balances.keys())
    for t in transactions:
        user_ids.update([t["from_user"], t["to_user"]])
    for s in paid_settlements:
        user_ids.update([s.from_user, s.to_user])
    users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
    usernames = {u.id: u.username for u in users}

    return SettlementResult(
        balances=[
            BalanceOut(
                user_id=uid, username=usernames.get(uid), balance=float(amount)
            )
            for uid, amount in sorted(
                balances.items(), key=lambda kv: kv[1], reverse=True
            )
        ],
        settlements=[_transaction_out(group_id, t, usernames) for t in transactions],
        paid_settlements=[_settlement_out(s, usernames) for s in paid_settlements],
    )


@router.post("/confirm", response_model=SettlementResult)
def confirm_settlement(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)

    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    has_expense = db.query(Expense.id).filter(Expense.group_id == group_id).first()
    if has_expense is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add an expense before settling",
        )

    balances = _compute_balances(db, group_id)
    transactions = calculate_settlements(balances)
    now = _utcnow()
    for t in transactions:
        db.add(
            Settlement(
                group_id=group_id,
                from_user=t["from_user"],
                to_user=t["to_user"],
                amount=t["amount"],
                is_paid=True,
                paid_at=now,
            )
        )
    group.settled_at = now
    group.settled_by = current_user.id
    db.commit()

    return get_settlements(group_id, current_user=current_user, db=db)


@router.post("/{settlement_id}/pay", response_model=SettlementOut)
def mark_paid(
    group_id: str,
    settlement_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)

    settlement = (
        db.query(Settlement)
        .filter(Settlement.id == settlement_id, Settlement.group_id == group_id)
        .first()
    )
    if settlement is None:
        balances = _compute_balances(db, group_id)
        transaction = next(
            (
                t
                for t in calculate_settlements(balances)
                if _draft_settlement_id(
                    group_id, t["from_user"], t["to_user"], t["amount"]
                )
                == settlement_id
            ),
            None,
        )
        if transaction is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Settlement not found"
            )
        settlement = Settlement(
            group_id=group_id,
            from_user=transaction["from_user"],
            to_user=transaction["to_user"],
            amount=transaction["amount"],
        )
        db.add(settlement)
    elif settlement.is_paid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Settlement is already paid",
        )
    if current_user.id not in (settlement.from_user, settlement.to_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the payer or payee can mark this settlement as paid",
        )

    settlement.is_paid = True
    settlement.paid_at = _utcnow()
    db.commit()
    db.refresh(settlement)

    users = (
        db.query(User)
        .filter(User.id.in_([settlement.from_user, settlement.to_user]))
        .all()
    )
    usernames = {u.id: u.username for u in users}
    return _settlement_out(settlement, usernames)

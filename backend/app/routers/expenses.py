from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.database import get_db
from app.models.expense import Expense, ExpenseSplit, SplitType
from app.models.group import Group, Membership
from app.models.user import User
from app.routers.groups import get_group_or_404, require_membership
from app.schemas.expense import ExpenseCreate, ExpenseOut, SplitOut

router = APIRouter(prefix="/api/groups/{group_id}/expenses", tags=["expenses"])

CENT = Decimal("0.01")


def _expense_out(expense: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=expense.id,
        group_id=expense.group_id,
        title=expense.title,
        amount=float(expense.amount),
        currency=expense.currency,
        split_type=expense.split_type,
        paid_by=expense.paid_by,
        paid_by_username=expense.payer.username if expense.payer else None,
        created_by=expense.created_by,
        created_at=expense.created_at,
        splits=[
            SplitOut(
                user_id=s.user_id,
                username=s.user.username if s.user else None,
                amount=float(s.amount),
            )
            for s in expense.splits
        ],
    )


def _build_splits(
    body: ExpenseCreate, member_ids: list[str]
) -> list[tuple[str, Decimal]]:
    total = body.amount.quantize(CENT)

    if body.split_type == SplitType.EQUAL:
        n = len(member_ids)
        base = (total / n).quantize(CENT, rounding="ROUND_DOWN")
        remainder_cents = int((total - base * n) / CENT)
        splits = []
        for i, user_id in enumerate(member_ids):
            share = base + (CENT if i < remainder_cents else Decimal("0"))
            splits.append((user_id, share))
        return splits

    if not body.splits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Custom split requires per-person amounts",
        )
    seen = set()
    splits = []
    for s in body.splits:
        if s.user_id not in member_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Split includes a user who is not a group member",
            )
        if s.user_id in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate user in splits",
            )
        seen.add(s.user_id)
        splits.append((s.user_id, s.amount.quantize(CENT)))

    if sum(amount for _, amount in splits) != total:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Split amounts must sum to the total amount",
        )
    return splits


@router.post("/", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    group_id: str,
    body: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    require_membership(db, group_id, current_user.id)

    member_ids = [
        m.user_id
        for m in db.query(Membership).filter(Membership.group_id == group_id).all()
    ]
    if body.paid_by not in member_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payer must be a group member",
        )

    splits = _build_splits(body, member_ids)

    expense = Expense(
        group_id=group_id,
        paid_by=body.paid_by,
        title=body.title.strip(),
        amount=body.amount.quantize(CENT),
        currency=body.currency.upper(),
        split_type=body.split_type,
        created_by=current_user.id,
    )
    db.add(expense)
    db.flush()
    for user_id, amount in splits:
        db.add(ExpenseSplit(expense_id=expense.id, user_id=user_id, amount=amount))
    db.commit()
    db.refresh(expense)
    return _expense_out(expense)


@router.get("/", response_model=list[ExpenseOut])
def list_expenses(
    group_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)
    expenses = (
        db.query(Expense)
        .options(joinedload(Expense.splits).joinedload(ExpenseSplit.user))
        .options(joinedload(Expense.payer))
        .filter(Expense.group_id == group_id)
        .order_by(Expense.created_at.desc())
        .all()
    )
    return [_expense_out(e) for e in expenses]


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    group_id: str,
    expense_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)
    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.group_id == group_id)
        .first()
    )
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        )
    if expense.created_by != current_user.id and group.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the expense creator or group creator can delete this expense",
        )
    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense_id).delete(
        synchronize_session=False
    )
    db.delete(expense)
    db.commit()

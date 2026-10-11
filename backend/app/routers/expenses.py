from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.database import get_db
from app.models.expense import Expense, ExpenseRevision, ExpenseSplit, SplitType
from app.services import fx
from app.services.settlement import add_splits, equal_split
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
        fx_rate=float(expense.fx_rate),
        amount_usd=float(expense.amount_usd),
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
    unit = fx.currency_unit(body.currency)
    if any(a % unit for a in [total, *(s.amount for s in body.splits or [])]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{body.currency} amounts must be whole numbers",
        )

    if body.split_type == SplitType.EQUAL:
        # Direct expenses reuse this helper and always split between exactly the
        # two people already in member_ids, so they carry no participants field.
        chosen = getattr(body, "participants", None)
        if chosen is None:
            return equal_split(total, member_ids, unit)
        participants = list(dict.fromkeys(chosen))
        if not participants:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pick at least one person to split between",
            )
        unknown = set(participants) - set(member_ids)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Split includes a user who is not a group member",
            )
        # Preserve the caller's member order so the extra rounding cents land
        # deterministically rather than in request order.
        ordered = [uid for uid in member_ids if uid in set(participants)]
        return equal_split(total, ordered, unit)

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
    # Fetch before taking the group lock; a cold cache means a network call.
    rate = fx.rate_for(body.currency)
    group = get_group_or_404(db, group_id, lock=True)
    if group.settled_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Group is already settled"
        )
    require_membership(db, group_id, current_user.id)

    member_ids = [
        m.user_id
        for m in db.query(Membership)
        .filter(Membership.group_id == group_id)
        .order_by(Membership.joined_at)
        .all()
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
        currency=body.currency,
        fx_rate=rate,
        amount_usd=fx.to_usd(body.amount.quantize(CENT), rate),
        split_type=body.split_type,
        created_by=current_user.id,
    )
    db.add(expense)
    db.flush()
    add_splits(db, expense, splits)
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


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    group_id: str,
    expense_id: str,
    body: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # An edit keeps the rate from when the expense was added; a new one is only
    # needed if the currency changes. Fetch it before taking the group lock.
    stored_currency = (
        db.query(Expense.currency)
        .filter(Expense.id == expense_id, Expense.group_id == group_id)
        .scalar()
    )
    new_rate = (
        fx.rate_for(body.currency)
        if stored_currency not in (None, body.currency)
        else None
    )
    group = get_group_or_404(db, group_id, lock=True)
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
            detail="Only the expense creator or group creator can edit this expense",
        )

    member_ids = [
        m.user_id
        for m in db.query(Membership)
        .filter(Membership.group_id == group_id)
        .order_by(Membership.joined_at)
        .all()
    ]
    if body.paid_by not in member_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payer must be a group member",
        )

    splits = _build_splits(body, member_ids)

    db.add(ExpenseRevision(
        expense_id=expense.id, changed_by=current_user.id,
        snapshot=_expense_out(expense).model_dump(mode="json"),
    ))
    if body.currency != expense.currency:
        # new_rate is None only if another edit changed the currency meanwhile.
        expense.fx_rate = new_rate or fx.rate_for(body.currency)
    expense.title = body.title.strip()
    expense.amount = body.amount.quantize(CENT)
    expense.currency = body.currency
    expense.amount_usd = fx.to_usd(expense.amount, expense.fx_rate)
    expense.split_type = body.split_type
    expense.paid_by = body.paid_by
    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense_id).delete(
        synchronize_session=False
    )
    add_splits(db, expense, splits)
    db.commit()
    db.refresh(expense)
    return _expense_out(expense)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    group_id: str,
    expense_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    group = get_group_or_404(db, group_id, lock=True)
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
    db.query(ExpenseRevision).filter(ExpenseRevision.expense_id == expense_id).delete(synchronize_session=False)
    db.delete(expense)
    db.commit()


@router.get("/{expense_id}/history")
def expense_history(
    group_id: str,
    expense_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_group_or_404(db, group_id)
    require_membership(db, group_id, current_user.id)
    if db.query(Expense.id).filter(Expense.id == expense_id, Expense.group_id == group_id).first() is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    rows = db.query(ExpenseRevision, User.username).join(
        User, User.id == ExpenseRevision.changed_by
    ).filter(ExpenseRevision.expense_id == expense_id).order_by(ExpenseRevision.changed_at.desc()).all()
    return [dict(id=r.id, expense_id=r.expense_id, changed_by=r.changed_by,
                 changed_by_username=username, changed_at=r.changed_at, snapshot=r.snapshot)
            for r, username in rows]

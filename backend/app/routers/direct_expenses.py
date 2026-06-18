from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.expense import Expense, ExpenseSplit
from app.models.user import User
from app.routers.expenses import _build_splits, _expense_out
from app.schemas.expense import ExpenseOut
from app.schemas.friend import DirectExpenseCreate
from app.services import friends as friends_svc

router = APIRouter(prefix="/api/direct-expenses", tags=["direct-expenses"])

CENT = Decimal("0.01")


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_direct_expense(
    body: DirectExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participants = set(body.participant_ids) | {body.paid_by}
    others = participants - {current_user.id}
    for uid in others:
        if not friends_svc.are_friends(db, current_user.id, uid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="All participants must be your friends",
            )
    if body.paid_by not in participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payer must be a participant",
        )

    member_ids = list(participants)
    splits = _build_splits(body, member_ids)

    expense = Expense(
        group_id=None,
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


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_direct_expense(
    expense_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    expense = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.group_id.is_(None))
        .first()
    )
    if expense is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        )
    if expense.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator can delete this expense",
        )
    db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == expense_id).delete(
        synchronize_session=False
    )
    db.delete(expense)
    db.commit()

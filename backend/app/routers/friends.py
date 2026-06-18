from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.database import get_db
from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User, utcnow
from app.routers.expenses import _expense_out
from app.schemas.expense import ExpenseOut
from app.schemas.friend import FriendOut, FriendRequestCreate, FriendRequestOut
from app.services import friends as friends_svc

router = APIRouter(prefix="/api/friends", tags=["friends"])


@router.post(
    "/requests", response_model=FriendRequestOut, status_code=status.HTTP_201_CREATED
)
def send_friend_request(
    body: FriendRequestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = (
        db.query(User).filter(User.phone_number == body.phone_number).first()
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No user with that phone number"
        )
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot add yourself",
        )
    if friends_svc.get_friendship(db, current_user.id, target.id) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A friend request already exists",
        )

    friendship = Friendship(requester_id=current_user.id, addressee_id=target.id)
    db.add(friendship)
    db.commit()
    db.refresh(friendship)
    return FriendRequestOut(
        id=friendship.id,
        requester_id=friendship.requester_id,
        requester_username=current_user.username,
        created_at=friendship.created_at,
    )


@router.get("/requests", response_model=list[FriendRequestOut])
def incoming_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Friendship)
        .filter(
            Friendship.addressee_id == current_user.id,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .order_by(Friendship.created_at.desc())
        .all()
    )
    requesters = (
        {
            u.id: u.username
            for u in db.query(User)
            .filter(User.id.in_([f.requester_id for f in rows]))
            .all()
        }
        if rows
        else {}
    )
    return [
        FriendRequestOut(
            id=f.id,
            requester_id=f.requester_id,
            requester_username=requesters.get(f.requester_id),
            created_at=f.created_at,
        )
        for f in rows
    ]


def _get_incoming_or_404(db: Session, friendship_id: str, user_id: str) -> Friendship:
    friendship = (
        db.query(Friendship)
        .filter(
            Friendship.id == friendship_id,
            Friendship.addressee_id == user_id,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .first()
    )
    if friendship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend request not found"
        )
    return friendship


@router.post("/requests/{friendship_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_request(
    friendship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = _get_incoming_or_404(db, friendship_id, current_user.id)
    friendship.status = FriendshipStatus.ACCEPTED
    friendship.responded_at = utcnow()
    db.commit()


@router.post("/requests/{friendship_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_request(
    friendship_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = _get_incoming_or_404(db, friendship_id, current_user.id)
    db.delete(friendship)
    db.commit()


@router.get("", response_model=list[FriendOut])
def list_friends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friend_ids = friends_svc.accepted_friend_ids(db, current_user.id)
    if not friend_ids:
        return []
    users = db.query(User).filter(User.id.in_(friend_ids)).all()
    return [
        FriendOut(
            id=u.id,
            username=u.username,
            phone_number=u.phone_number,
            net_balance=float(friends_svc.friend_balance(db, current_user.id, u.id)),
        )
        for u in users
    ]


@router.delete("/{friend_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_friend(
    friend_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    friendship = friends_svc.get_friendship(db, current_user.id, friend_id)
    if friendship is None or friendship.status != FriendshipStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found"
        )
    if friends_svc.friend_balance(db, current_user.id, friend_id) != Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Settle the balance before removing this friend",
        )
    db.delete(friendship)
    db.commit()


@router.post("/{friend_id}/settle")
def settle_with_friend(
    friend_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not friends_svc.are_friends(db, current_user.id, friend_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found"
        )
    balance = friends_svc.friend_balance(db, current_user.id, friend_id)
    if balance == Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nothing to settle",
        )
    # Positive balance: friend owes me -> friend pays me (from=friend, to=me).
    # Negative balance: I owe friend -> I pay friend (from=me, to=friend).
    if balance > 0:
        from_user, to_user, amount = friend_id, current_user.id, balance
    else:
        from_user, to_user, amount = current_user.id, friend_id, -balance
    db.add(
        Settlement(
            group_id=None,
            from_user=from_user,
            to_user=to_user,
            amount=amount,
            is_paid=True,
            paid_at=utcnow(),
        )
    )
    db.commit()
    return {"settled_amount": float(amount)}


@router.get("/{friend_id}/expenses", response_model=list[ExpenseOut])
def friend_expenses(
    friend_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not friends_svc.are_friends(db, current_user.id, friend_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Friend not found"
        )
    # Direct expenses where both the caller and the friend appear in the splits.
    pair_expense_ids = (
        db.query(ExpenseSplit.expense_id)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(Expense.group_id.is_(None))
        .filter(ExpenseSplit.user_id.in_([current_user.id, friend_id]))
        .group_by(ExpenseSplit.expense_id)
        .having(func.count(func.distinct(ExpenseSplit.user_id)) == 2)
        .all()
    )
    ids = [row[0] for row in pair_expense_ids]
    if not ids:
        return []
    expenses = (
        db.query(Expense)
        .options(joinedload(Expense.splits).joinedload(ExpenseSplit.user))
        .options(joinedload(Expense.payer))
        .filter(Expense.id.in_(ids))
        .order_by(Expense.created_at.desc())
        .all()
    )
    return [_expense_out(e) for e in expenses]

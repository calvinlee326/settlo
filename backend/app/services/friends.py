from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.friendship import Friendship, FriendshipStatus

CENT = Decimal("0.01")


def get_friendship(db: Session, user_a: str, user_b: str) -> Friendship | None:
    return (
        db.query(Friendship)
        .filter(
            or_(
                and_(
                    Friendship.requester_id == user_a,
                    Friendship.addressee_id == user_b,
                ),
                and_(
                    Friendship.requester_id == user_b,
                    Friendship.addressee_id == user_a,
                ),
            )
        )
        .first()
    )


def are_friends(db: Session, user_a: str, user_b: str) -> bool:
    f = get_friendship(db, user_a, user_b)
    return f is not None and f.status == FriendshipStatus.ACCEPTED


def accepted_friend_ids(db: Session, user_id: str) -> set[str]:
    rows = (
        db.query(Friendship)
        .filter(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            ),
        )
        .all()
    )
    ids: set[str] = set()
    for f in rows:
        ids.add(f.addressee_id if f.requester_id == user_id else f.requester_id)
    return ids


def friend_balance(db: Session, user_id: str, friend_id: str) -> Decimal:
    """Net for the (user_id, friend_id) pair across direct rows.

    Positive = friend owes user_id.
    """
    bal = Decimal("0")

    # Direct expenses user paid -> friend's share is owed to user.
    paid_by_user = (
        db.query(ExpenseSplit.amount)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(
            Expense.group_id.is_(None),
            Expense.paid_by == user_id,
            ExpenseSplit.user_id == friend_id,
        )
        .all()
    )
    for (amount,) in paid_by_user:
        bal += Decimal(amount)

    # Direct expenses friend paid -> user's share is owed to friend.
    paid_by_friend = (
        db.query(ExpenseSplit.amount)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(
            Expense.group_id.is_(None),
            Expense.paid_by == friend_id,
            ExpenseSplit.user_id == user_id,
        )
        .all()
    )
    for (amount,) in paid_by_friend:
        bal -= Decimal(amount)

    # Direct settlements between the pair (same sign rule as group balances).
    settlements = (
        db.query(Settlement)
        .filter(
            Settlement.group_id.is_(None),
            Settlement.is_paid.is_(True),
            or_(
                and_(
                    Settlement.from_user == user_id,
                    Settlement.to_user == friend_id,
                ),
                and_(
                    Settlement.from_user == friend_id,
                    Settlement.to_user == user_id,
                ),
            ),
        )
        .all()
    )
    for s in settlements:
        if s.from_user == user_id:
            bal += Decimal(s.amount)
        else:
            bal -= Decimal(s.amount)

    return bal.quantize(CENT)

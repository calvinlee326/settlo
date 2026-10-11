from decimal import Decimal

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseSplit, Settlement
from app.models.friendship import Friendship, FriendshipStatus
from app.models.user import User
from app.schemas.user import UserLookup

CENT = Decimal("0.01")


def find_user(db: Session, lookup: UserLookup) -> User | None:
    return db.query(User).filter(User.handle == lookup.handle).first()


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


def friend_balances(
    db: Session, user_id: str, friend_ids: list[str]
) -> dict[str, Decimal]:
    """Net per friend across direct rows, in four queries however many friends.

    Positive = friend owes user_id.
    """
    balances = {fid: Decimal("0") for fid in friend_ids}
    if not friend_ids:
        return balances

    # Direct expenses user paid -> each friend's share is owed to user.
    owed_to_user = (
        db.query(ExpenseSplit.user_id, func.sum(ExpenseSplit.amount_usd))
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(
            Expense.group_id.is_(None),
            Expense.paid_by == user_id,
            ExpenseSplit.user_id.in_(friend_ids),
        )
        .group_by(ExpenseSplit.user_id)
        .all()
    )
    # Direct expenses a friend paid -> user's share is owed to that friend.
    owed_by_user = (
        db.query(Expense.paid_by, func.sum(ExpenseSplit.amount_usd))
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(
            Expense.group_id.is_(None),
            Expense.paid_by.in_(friend_ids),
            ExpenseSplit.user_id == user_id,
        )
        .group_by(Expense.paid_by)
        .all()
    )
    # Direct settlements between the pair (same sign rule as group balances).
    paid_by_user = (
        db.query(Settlement.to_user, func.sum(Settlement.amount))
        .filter(
            Settlement.group_id.is_(None),
            Settlement.is_paid.is_(True),
            Settlement.from_user == user_id,
            Settlement.to_user.in_(friend_ids),
        )
        .group_by(Settlement.to_user)
        .all()
    )
    paid_to_user = (
        db.query(Settlement.from_user, func.sum(Settlement.amount))
        .filter(
            Settlement.group_id.is_(None),
            Settlement.is_paid.is_(True),
            Settlement.to_user == user_id,
            Settlement.from_user.in_(friend_ids),
        )
        .group_by(Settlement.from_user)
        .all()
    )

    for fid, total in owed_to_user + paid_by_user:
        balances[fid] += Decimal(total or 0)
    for fid, total in owed_by_user + paid_to_user:
        balances[fid] -= Decimal(total or 0)
    return {fid: amount.quantize(CENT) for fid, amount in balances.items()}


def friend_balance(db: Session, user_id: str, friend_id: str) -> Decimal:
    """Positive = friend owes user_id."""
    return friend_balances(db, user_id, [friend_id])[friend_id]

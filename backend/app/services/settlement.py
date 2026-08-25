import heapq
from decimal import Decimal

from sqlalchemy import func, or_

from app.models.expense import Expense, ExpenseSplit, Settlement

CENT = Decimal("0.01")


def equal_split(total: Decimal, member_ids: list[str]) -> list[tuple[str, Decimal]]:
    total = total.quantize(CENT)
    n = len(member_ids)
    base = (total / n).quantize(CENT, rounding="ROUND_DOWN")
    remainder_cents = int((total - base * n) / CENT)
    shares: list[tuple[str, Decimal]] = []
    for i, user_id in enumerate(member_ids):
        share = base + (CENT if i < remainder_cents else Decimal("0"))
        shares.append((user_id, share))
    return shares


def calculate_settlements(balances: dict[str, Decimal]) -> list[dict]:
    """Greedy min-transaction settlement.

    balances maps user_id -> net amount (paid - owed).
    Positive = should receive money, negative = should pay.
    Returns [{"from_user", "to_user", "amount"}, ...] with Decimal amounts.
    """
    creditors: list[tuple[Decimal, str]] = []
    debtors: list[tuple[Decimal, str]] = []

    for user_id, amount in balances.items():
        amount = amount.quantize(CENT)
        if amount >= CENT:
            heapq.heappush(creditors, (-amount, user_id))
        elif amount <= -CENT:
            heapq.heappush(debtors, (amount, user_id))

    transactions: list[dict] = []
    while creditors and debtors:
        neg_credit, creditor = heapq.heappop(creditors)
        debt_amount, debtor = heapq.heappop(debtors)
        credit = -neg_credit
        debt = -debt_amount

        settled = min(credit, debt)
        transactions.append(
            {"from_user": debtor, "to_user": creditor, "amount": settled}
        )

        remaining_credit = credit - settled
        remaining_debt = debt - settled
        if remaining_credit >= CENT:
            heapq.heappush(creditors, (-remaining_credit, creditor))
        if remaining_debt >= CENT:
            heapq.heappush(debtors, (-remaining_debt, debtor))

    return transactions


def net_balances_by_group(
    db, user_id: str, group_ids: list[str]
) -> dict[str, Decimal]:
    """Net balance (paid - owed, less anything already settled) per group.

    Mirrors the per-group balance math in the settlements router, batched so the
    group list can show one number per group without a query per group.
    """
    if not group_ids:
        return {}

    balances: dict[str, Decimal] = {gid: Decimal("0") for gid in group_ids}

    paid = (
        db.query(Expense.group_id, func.sum(Expense.amount))
        .filter(Expense.group_id.in_(group_ids), Expense.paid_by == user_id)
        .group_by(Expense.group_id)
        .all()
    )
    for gid, total in paid:
        balances[gid] += Decimal(total or 0)

    owed = (
        db.query(Expense.group_id, func.sum(ExpenseSplit.amount))
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .filter(Expense.group_id.in_(group_ids), ExpenseSplit.user_id == user_id)
        .group_by(Expense.group_id)
        .all()
    )
    for gid, total in owed:
        balances[gid] -= Decimal(total or 0)

    settled = (
        db.query(Settlement.group_id, Settlement.from_user, func.sum(Settlement.amount))
        .filter(
            Settlement.group_id.in_(group_ids),
            Settlement.is_paid.is_(True),
            or_(Settlement.from_user == user_id, Settlement.to_user == user_id),
        )
        .group_by(Settlement.group_id, Settlement.from_user)
        .all()
    )
    for gid, from_user, total in settled:
        if from_user == user_id:
            balances[gid] += Decimal(total or 0)
        else:
            balances[gid] -= Decimal(total or 0)

    return {gid: amount.quantize(CENT) for gid, amount in balances.items()}

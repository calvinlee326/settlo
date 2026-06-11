import heapq
from decimal import Decimal

CENT = Decimal("0.01")


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

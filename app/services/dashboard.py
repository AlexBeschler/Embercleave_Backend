from datetime import datetime, timezone

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.services.budgets import list_budgets


def _sort_key(txn: dict) -> datetime:
    value = txn.get("transactedAt") or txn.get("postedDate")
    return value if value is not None else datetime.min.replace(tzinfo=timezone.utc)


def get_dashboard(db: firestore.Client, uid: str) -> dict:
    """architecture.md §3.3.3: cash balance from the checking-type
    account(s); per-budget spent/left computed from transactions where
    periodId == activePeriodId AND status == accepted, grouped by budgetId;
    the 5 most recent transactions in the active period, any status.
    """
    user_ref = db.collection("users").document(uid)
    user_data = user_ref.get().to_dict() or {}
    active_period_id = user_data.get("activePeriodId")

    checking_accounts = [
        doc.to_dict()
        for doc in user_ref.collection("accounts").where(filter=FieldFilter("type", "==", "checking")).stream()
    ]
    cash_balance = sum(a.get("balance", 0) for a in checking_accounts)

    period_transactions = [
        {"id": doc.id, **doc.to_dict()}
        for doc in user_ref.collection("transactions")
        .where(filter=FieldFilter("periodId", "==", active_period_id))
        .stream()
    ]

    # Plaid's amount convention (confirmed against live Sandbox data,
    # architecture.md §11): positive = money out of the account (a spend),
    # negative = money in (a refund/credit) — summing raw amounts nets
    # refunds against spend for the period.
    spent_by_budget: dict[str, float] = {}
    for txn in period_transactions:
        if txn.get("status") == "accepted" and txn.get("budgetId"):
            spent_by_budget[txn["budgetId"]] = spent_by_budget.get(txn["budgetId"], 0) + txn["amount"]

    budgets = [
        {**b, "spent": spent_by_budget.get(b["id"], 0), "left": b["amount"] - spent_by_budget.get(b["id"], 0)}
        for b in list_budgets(db, uid)
    ]

    recent_transactions = sorted(period_transactions, key=_sort_key, reverse=True)[:5]

    return {"cashBalance": cash_balance, "budgets": budgets, "recentTransactions": recent_transactions}

from datetime import datetime, timezone

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.errors import NotFoundError


def _transactions_ref(db: firestore.Client, uid: str) -> firestore.CollectionReference:
    return db.collection("users").document(uid).collection("transactions")


def _sort_key(txn: dict) -> datetime:
    value = txn.get("transactedAt") or txn.get("postedDate")
    return value if value is not None else datetime.min.replace(tzinfo=timezone.utc)


def list_transactions(db: firestore.Client, uid: str, *, status: str | None) -> list[dict]:
    """architecture.md §3.3.3: scoped to activePeriodId. With no `status`
    filter, TransactionView's default list excludes rejected transactions
    (those have their own list, requirements.md TransactionView); an
    explicit `status` filter (e.g. "rejected") overrides that."""
    user_data = db.collection("users").document(uid).get().to_dict() or {}
    active_period_id = user_data.get("activePeriodId")

    query = _transactions_ref(db, uid).where(filter=FieldFilter("periodId", "==", active_period_id))
    transactions = [{"id": doc.id, **doc.to_dict()} for doc in query.stream()]

    if status is not None:
        transactions = [t for t in transactions if t.get("status") == status]
    else:
        transactions = [t for t in transactions if t.get("status") != "rejected"]

    transactions.sort(key=_sort_key, reverse=True)
    return transactions


def accept_transaction(db: firestore.Client, uid: str, transaction_id: str, budget_id: str) -> dict:
    """architecture.md §3.3.3: validates budgetId belongs to the user."""
    budget_ref = db.collection("users").document(uid).collection("budgets").document(budget_id)
    if not budget_ref.get().exists:
        raise NotFoundError

    txn_ref = _transactions_ref(db, uid).document(transaction_id)
    snapshot = txn_ref.get()
    if not snapshot.exists:
        raise NotFoundError

    updates = {"status": "accepted", "budgetId": budget_id, "updatedAt": firestore.SERVER_TIMESTAMP}
    txn_ref.update(updates)
    return {"id": transaction_id, **{**snapshot.to_dict(), **updates}}


def reject_transaction(db: firestore.Client, uid: str, transaction_id: str) -> dict:
    txn_ref = _transactions_ref(db, uid).document(transaction_id)
    snapshot = txn_ref.get()
    if not snapshot.exists:
        raise NotFoundError

    updates = {"status": "rejected", "budgetId": None, "updatedAt": firestore.SERVER_TIMESTAMP}
    txn_ref.update(updates)
    return {"id": transaction_id, **{**snapshot.to_dict(), **updates}}


def unreject_transaction(db: firestore.Client, uid: str, transaction_id: str) -> dict:
    txn_ref = _transactions_ref(db, uid).document(transaction_id)
    snapshot = txn_ref.get()
    if not snapshot.exists:
        raise NotFoundError

    updates = {"status": "uncategorized", "budgetId": None, "updatedAt": firestore.SERVER_TIMESTAMP}
    txn_ref.update(updates)
    return {"id": transaction_id, **{**snapshot.to_dict(), **updates}}

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.errors import NotFoundError


def _budgets_ref(db: firestore.Client, uid: str) -> firestore.CollectionReference:
    return db.collection("users").document(uid).collection("budgets")


def list_budgets(db: firestore.Client, uid: str) -> list[dict]:
    """architecture.md §3.3.3: ordered by the `order` field."""
    budgets = [{"id": doc.id, **doc.to_dict()} for doc in _budgets_ref(db, uid).stream()]
    budgets.sort(key=lambda b: b["order"])
    return budgets


def create_budget(db: firestore.Client, uid: str, name: str, amount: float) -> dict:
    budgets_ref = _budgets_ref(db, uid)
    existing_orders = [doc.to_dict().get("order", 0) for doc in budgets_ref.stream()]
    order = max(existing_orders, default=-1) + 1

    now = firestore.SERVER_TIMESTAMP
    budget_ref = budgets_ref.document()
    budget_ref.set({"name": name, "amount": amount, "order": order, "createdAt": now, "updatedAt": now})
    return {"id": budget_ref.id, "name": name, "amount": amount, "order": order}


def patch_budget(db: firestore.Client, uid: str, budget_id: str, *, name: str | None, amount: float | None) -> dict:
    """architecture.md §8: PATCH /budgets/{id} handles both amount edits
    (effective immediately, mid-period) and renames — same endpoint,
    different fields."""
    budget_ref = _budgets_ref(db, uid).document(budget_id)
    snapshot = budget_ref.get()
    if not snapshot.exists:
        raise NotFoundError

    updates = {"updatedAt": firestore.SERVER_TIMESTAMP}
    if name is not None:
        updates["name"] = name
    if amount is not None:
        updates["amount"] = amount
    budget_ref.update(updates)

    data = {**snapshot.to_dict(), **updates}
    return {"id": budget_id, "name": data["name"], "amount": data["amount"], "order": data["order"]}


def reorder_budgets(db: firestore.Client, uid: str, ordered_ids: list[str]) -> None:
    budgets_ref = _budgets_ref(db, uid)
    existing_ids = {doc.id for doc in budgets_ref.stream()}
    if not set(ordered_ids).issubset(existing_ids):
        raise NotFoundError

    for index, budget_id in enumerate(ordered_ids):
        budgets_ref.document(budget_id).update({"order": index, "updatedAt": firestore.SERVER_TIMESTAMP})


def delete_budget(db: firestore.Client, uid: str, budget_id: str) -> None:
    """architecture.md §8/§4: deleting a budget cascades — every transaction
    with this budgetId (any period, since history isn't scoped to the
    active period) is reset to uncategorized."""
    budget_ref = _budgets_ref(db, uid).document(budget_id)
    if not budget_ref.get().exists:
        raise NotFoundError

    transactions_ref = db.collection("users").document(uid).collection("transactions")
    query = transactions_ref.where(filter=FieldFilter("budgetId", "==", budget_id))
    for doc in query.stream():
        doc.reference.update({"status": "uncategorized", "budgetId": None, "updatedAt": firestore.SERVER_TIMESTAMP})

    budget_ref.delete()

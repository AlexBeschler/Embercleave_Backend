from google.cloud import firestore


def clear_month(db: firestore.Client, uid: str) -> dict:
    """architecture.md §3.3.3 Clear Month: archive the active period and
    start a new one. Transactions are left untouched — every read already
    scopes by activePeriodId, so archived-period transactions simply stop
    appearing in active views (soft-archive, no data migration later).
    Batched so the new-period create, old-period archive, and user pointer
    update land atomically.
    """
    user_ref = db.collection("users").document(uid)
    user_data = user_ref.get().to_dict() or {}
    old_period_id = user_data.get("activePeriodId")

    now = firestore.SERVER_TIMESTAMP
    periods_ref = user_ref.collection("periods")
    new_period_ref = periods_ref.document()

    batch = db.batch()
    batch.set(new_period_ref, {"startDate": now, "clearedAt": None, "status": "active"})
    if old_period_id:
        batch.update(periods_ref.document(old_period_id), {"status": "archived", "clearedAt": now})
    batch.update(user_ref, {"activePeriodId": new_period_ref.id, "updatedAt": now})
    batch.commit()

    return {"activePeriodId": new_period_ref.id}

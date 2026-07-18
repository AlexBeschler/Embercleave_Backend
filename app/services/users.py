from google.cloud import firestore


def bootstrap_user(db: firestore.Client, uid: str, email: str | None) -> dict:
    """Idempotent per architecture.md §3.1: creates users/{uid} and an
    initial active period only on first call; subsequent calls are a
    no-op that just returns current state. Wrapped in a transaction so
    two concurrent bootstrap calls for the same new user (e.g. two
    devices signing in at once) can't create two periods.
    """
    user_ref = db.collection("users").document(uid)
    periods_ref = user_ref.collection("periods")
    transaction = db.transaction()

    @firestore.transactional
    def _run(transaction: firestore.Transaction) -> dict:
        snapshot = user_ref.get(transaction=transaction)
        if snapshot.exists:
            return snapshot.to_dict()

        now = firestore.SERVER_TIMESTAMP
        period_ref = periods_ref.document()
        transaction.set(period_ref, {
            "startDate": now,
            "clearedAt": None,
            "status": "active",
        })

        user_data = {
            "email": email,
            "connectionStatus": "not_connected",
            "plaidItemId": None,
            "plaidAccessToken": None,
            "plaidCursor": None,
            "activePeriodId": period_ref.id,
            "createdAt": now,
            "updatedAt": now,
        }
        transaction.set(user_ref, user_data)
        return {**user_data, "activePeriodId": period_ref.id}

    return _run(transaction)

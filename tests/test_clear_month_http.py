from fastapi.testclient import TestClient

from app.auth import get_current_user_claims
from app.main import app

OLD_PERIOD = "period-old"


def _cleanup(db, uid, new_period_id=None):
    user_ref = db.collection("users").document(uid)
    for sub in ("budgets", "transactions"):
        for doc in user_ref.collection(sub).stream():
            doc.reference.delete()
    for doc in user_ref.collection("periods").stream():
        doc.reference.delete()
    user_ref.delete()


def _seed_user(db, uid):
    db.collection("users").document(uid).set({"activePeriodId": OLD_PERIOD})
    db.collection("users").document(uid).collection("periods").document(OLD_PERIOD).set(
        {"startDate": None, "clearedAt": None, "status": "active"}
    )


def _authed_client(test_uid):
    app.dependency_overrides[get_current_user_claims] = lambda: {"uid": test_uid, "email": "test@example.com"}
    return TestClient(app)


def test_clear_month_archives_old_period_and_starts_new_one(db, test_uid):
    new_period_id = None
    try:
        _seed_user(db, test_uid)
        old_txn_ref = db.collection("users").document(test_uid).collection("transactions").document("t-1")
        old_txn_ref.set(
            {
                "accountId": "a",
                "accountType": "checking",
                "description": "Old purchase",
                "amount": 10.0,
                "postedDate": None,
                "transactedAt": None,
                "pending": False,
                "status": "uncategorized",
                "budgetId": None,
                "periodId": OLD_PERIOD,
            }
        )

        client = _authed_client(test_uid)
        response = client.post("/clear-month")
        assert response.status_code == 200
        new_period_id = response.json()["activePeriodId"]
        assert new_period_id != OLD_PERIOD

        user = db.collection("users").document(test_uid).get().to_dict()
        assert user["activePeriodId"] == new_period_id

        periods_ref = db.collection("users").document(test_uid).collection("periods")
        old_period = periods_ref.document(OLD_PERIOD).get().to_dict()
        assert old_period["status"] == "archived"
        assert old_period["clearedAt"] is not None

        new_period = periods_ref.document(new_period_id).get().to_dict()
        assert new_period["status"] == "active"

        # Old transaction is untouched, not migrated or deleted.
        old_txn = old_txn_ref.get().to_dict()
        assert old_txn["periodId"] == OLD_PERIOD

        # And no longer shows up in the active-period transaction list.
        listed = client.get("/transactions").json()
        assert listed == []
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid, new_period_id=new_period_id)

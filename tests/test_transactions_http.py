from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth import get_current_user_claims
from app.main import app

ACTIVE_PERIOD = "period-active"
OTHER_PERIOD = "period-archived"


def _cleanup(db, uid):
    user_ref = db.collection("users").document(uid)
    for sub in ("budgets", "transactions"):
        for doc in user_ref.collection(sub).stream():
            doc.reference.delete()
    user_ref.delete()


def _seed_user(db, uid):
    db.collection("users").document(uid).set({"activePeriodId": ACTIVE_PERIOD})


def _seed_txn(db, uid, txn_id, **overrides):
    now = datetime.now(timezone.utc)
    data = {
        "accountId": "acct-1",
        "accountType": "checking",
        "description": "Coffee Shop",
        "amount": -5.0,
        "postedDate": now,
        "transactedAt": now,
        "pending": False,
        "status": "uncategorized",
        "budgetId": None,
        "periodId": ACTIVE_PERIOD,
    }
    data.update(overrides)
    db.collection("users").document(uid).collection("transactions").document(txn_id).set(data)


def _authed_client(test_uid):
    app.dependency_overrides[get_current_user_claims] = lambda: {"uid": test_uid, "email": "test@example.com"}
    return TestClient(app)


def test_list_transactions_excludes_rejected_and_other_periods(db, test_uid):
    try:
        _seed_user(db, test_uid)
        now = datetime.now(timezone.utc)
        _seed_txn(db, test_uid, "t-uncategorized", transactedAt=now)
        _seed_txn(db, test_uid, "t-accepted", status="accepted", budgetId="b1", transactedAt=now - timedelta(minutes=1))
        _seed_txn(db, test_uid, "t-rejected", status="rejected", transactedAt=now - timedelta(minutes=2))
        _seed_txn(db, test_uid, "t-other-period", periodId=OTHER_PERIOD, transactedAt=now)

        client = _authed_client(test_uid)
        response = client.get("/transactions")
        assert response.status_code == 200
        ids = [t["id"] for t in response.json()]
        assert ids == ["t-uncategorized", "t-accepted"]
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_list_transactions_status_rejected_filter(db, test_uid):
    try:
        _seed_user(db, test_uid)
        _seed_txn(db, test_uid, "t-uncategorized")
        _seed_txn(db, test_uid, "t-rejected", status="rejected")

        client = _authed_client(test_uid)
        response = client.get("/transactions", params={"status": "rejected"})
        assert response.status_code == 200
        ids = [t["id"] for t in response.json()]
        assert ids == ["t-rejected"]
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_accept_transaction_validates_budget_and_sets_fields(db, test_uid):
    try:
        _seed_user(db, test_uid)
        _seed_txn(db, test_uid, "t-1")
        client = _authed_client(test_uid)
        budget_id = client.post("/budgets", json={"name": "Coffee", "amount": 50}).json()["id"]

        response = client.post("/transactions/t-1/accept", json={"budgetId": budget_id})
        assert response.status_code == 200
        assert response.json()["status"] == "accepted"
        assert response.json()["budgetId"] == budget_id
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_accept_transaction_with_unknown_budget_returns_404(db, test_uid):
    try:
        _seed_user(db, test_uid)
        _seed_txn(db, test_uid, "t-1")
        client = _authed_client(test_uid)

        response = client.post("/transactions/t-1/accept", json={"budgetId": "bogus"})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_accept_missing_transaction_returns_404(db, test_uid):
    try:
        _seed_user(db, test_uid)
        client = _authed_client(test_uid)
        budget_id = client.post("/budgets", json={"name": "Coffee", "amount": 50}).json()["id"]

        response = client.post("/transactions/does-not-exist/accept", json={"budgetId": budget_id})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_reject_and_unreject_transaction(db, test_uid):
    try:
        _seed_user(db, test_uid)
        _seed_txn(db, test_uid, "t-1", status="accepted", budgetId="b1")
        client = _authed_client(test_uid)

        reject_response = client.post("/transactions/t-1/reject")
        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "rejected"
        assert reject_response.json()["budgetId"] is None

        unreject_response = client.post("/transactions/t-1/unreject")
        assert unreject_response.status_code == 200
        assert unreject_response.json()["status"] == "uncategorized"
        assert unreject_response.json()["budgetId"] is None
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_reject_missing_transaction_returns_404(test_uid):
    try:
        client = _authed_client(test_uid)
        response = client.post("/transactions/does-not-exist/reject")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()

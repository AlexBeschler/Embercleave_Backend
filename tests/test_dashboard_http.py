from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth import get_current_user_claims
from app.main import app

ACTIVE_PERIOD = "period-active"


def _cleanup(db, uid):
    user_ref = db.collection("users").document(uid)
    for sub in ("budgets", "transactions", "accounts"):
        for doc in user_ref.collection(sub).stream():
            doc.reference.delete()
    user_ref.delete()


def _seed_user(db, uid):
    db.collection("users").document(uid).set({"activePeriodId": ACTIVE_PERIOD})


def _seed_account(db, uid, account_id, **overrides):
    data = {"type": "checking", "name": "Checking", "balance": 0, "availableBalance": None}
    data.update(overrides)
    db.collection("users").document(uid).collection("accounts").document(account_id).set(data)


def _seed_txn(db, uid, txn_id, **overrides):
    now = datetime.now(timezone.utc)
    data = {
        "accountId": "acct-1",
        "accountType": "checking",
        "description": "Coffee Shop",
        "amount": 5.0,
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


def test_dashboard_cash_balance_sums_checking_accounts(db, test_uid):
    try:
        _seed_user(db, test_uid)
        _seed_account(db, test_uid, "checking-1", balance=1200.50)
        _seed_account(db, test_uid, "credit-1", type="credit_card", balance=300)

        client = _authed_client(test_uid)
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert response.json()["cashBalance"] == 1200.50
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_dashboard_budget_spent_left_nets_refunds(db, test_uid):
    try:
        _seed_user(db, test_uid)
        client = _authed_client(test_uid)
        budget_id = client.post("/budgets", json={"name": "Groceries", "amount": 400}).json()["id"]

        _seed_txn(db, test_uid, "spend-1", status="accepted", budgetId=budget_id, amount=60)
        _seed_txn(db, test_uid, "refund-1", status="accepted", budgetId=budget_id, amount=-10)
        _seed_txn(db, test_uid, "uncategorized-1", status="uncategorized", amount=25)
        _seed_txn(db, test_uid, "other-budget", status="accepted", budgetId="different-budget", amount=100)

        response = client.get("/dashboard")
        assert response.status_code == 200
        budgets = {b["id"]: b for b in response.json()["budgets"]}
        assert budgets[budget_id]["spent"] == 50
        assert budgets[budget_id]["left"] == 350
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_dashboard_recent_transactions_limited_to_five_most_recent(db, test_uid):
    try:
        _seed_user(db, test_uid)
        now = datetime.now(timezone.utc)
        for i in range(7):
            _seed_txn(db, test_uid, f"t-{i}", transactedAt=now - timedelta(minutes=i))

        client = _authed_client(test_uid)
        response = client.get("/dashboard")
        recent = response.json()["recentTransactions"]
        assert [t["id"] for t in recent] == ["t-0", "t-1", "t-2", "t-3", "t-4"]
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)

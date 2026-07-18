from fastapi.testclient import TestClient

from app.auth import get_current_user_claims
from app.main import app


def _cleanup(db, uid):
    user_ref = db.collection("users").document(uid)
    for sub in ("budgets", "transactions"):
        for doc in user_ref.collection(sub).stream():
            doc.reference.delete()
    user_ref.delete()


def _authed_client(test_uid):
    app.dependency_overrides[get_current_user_claims] = lambda: {"uid": test_uid, "email": "test@example.com"}
    return TestClient(app)


def test_create_and_list_budgets(db, test_uid):
    try:
        client = _authed_client(test_uid)
        r1 = client.post("/budgets", json={"name": "Groceries", "amount": 400})
        assert r1.status_code == 200
        assert r1.json()["name"] == "Groceries"
        assert r1.json()["amount"] == 400
        assert r1.json()["order"] == 0

        r2 = client.post("/budgets", json={"name": "Gas", "amount": 150})
        assert r2.json()["order"] == 1

        listed = client.get("/budgets").json()
        assert [b["name"] for b in listed] == ["Groceries", "Gas"]
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_patch_budget_amount_and_name(db, test_uid):
    try:
        client = _authed_client(test_uid)
        budget_id = client.post("/budgets", json={"name": "Groceries", "amount": 400}).json()["id"]

        response = client.patch(f"/budgets/{budget_id}", json={"amount": 350})
        assert response.status_code == 200
        assert response.json()["amount"] == 350
        assert response.json()["name"] == "Groceries"

        response = client.patch(f"/budgets/{budget_id}", json={"name": "Food"})
        assert response.json()["name"] == "Food"
        assert response.json()["amount"] == 350
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_patch_missing_budget_returns_404(test_uid):
    try:
        client = _authed_client(test_uid)
        response = client.patch("/budgets/does-not-exist", json={"amount": 10})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_reorder_budgets(db, test_uid):
    try:
        client = _authed_client(test_uid)
        a = client.post("/budgets", json={"name": "A", "amount": 1}).json()["id"]
        b = client.post("/budgets", json={"name": "B", "amount": 1}).json()["id"]

        response = client.post("/budgets/reorder", json={"orderedIds": [b, a]})
        assert response.status_code == 200

        listed = client.get("/budgets").json()
        assert [item["id"] for item in listed] == [b, a]
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_reorder_with_unknown_id_returns_404(db, test_uid):
    try:
        client = _authed_client(test_uid)
        a = client.post("/budgets", json={"name": "A", "amount": 1}).json()["id"]

        response = client.post("/budgets/reorder", json={"orderedIds": [a, "bogus"]})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_delete_budget_cascades_transactions_to_uncategorized(db, test_uid):
    try:
        client = _authed_client(test_uid)
        budget_id = client.post("/budgets", json={"name": "Groceries", "amount": 400}).json()["id"]

        txn_ref = db.collection("users").document(test_uid).collection("transactions").document("txn-1")
        txn_ref.set({"status": "accepted", "budgetId": budget_id, "amount": -20, "periodId": "period-1"})

        response = client.delete(f"/budgets/{budget_id}")
        assert response.status_code == 200

        assert not db.collection("users").document(test_uid).collection("budgets").document(budget_id).get().exists

        txn = txn_ref.get().to_dict()
        assert txn["status"] == "uncategorized"
        assert txn["budgetId"] is None
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid)


def test_delete_missing_budget_returns_404(test_uid):
    try:
        client = _authed_client(test_uid)
        response = client.delete("/budgets/does-not-exist")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()

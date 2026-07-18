"""End-to-end test against the real Plaid Sandbox API (no stubbing) and the
real dev Firestore database. Requires embercleave-plaid-secret-dev to hold a
real Plaid Sandbox secret (see README.md)."""

import time

from fastapi.testclient import TestClient
from plaid.model.products import Products
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest

from app.auth import get_current_user_claims
from app.main import app
from app.plaid_client import get_plaid_client
from app.services.plaid_sync import sync_user_transactions


def _cleanup(db, uid, item_id=None):
    user_ref = db.collection("users").document(uid)
    for sub in ("accounts", "transactions", "periods"):
        for doc in user_ref.collection(sub).stream():
            doc.reference.delete()
    user_ref.delete()
    if item_id:
        db.collection("enrollments").document(item_id).delete()


def test_connect_bank_and_sync_against_real_plaid_sandbox(db, test_uid):
    """Drives a real /sandbox/public_token/create -> POST /bank-connection
    round trip with no mocking of the Plaid HTTP layer, then verifies
    accounts and transactions land in real Firestore."""
    db.collection("users").document(test_uid).set(
        {
            "email": "test@example.com",
            "connectionStatus": "not_connected",
            "plaidItemId": None,
            "plaidAccessToken": None,
            "plaidCursor": None,
            "activePeriodId": "period-1",
        }
    )

    sandbox_request = SandboxPublicTokenCreateRequest(
        institution_id="ins_109508",  # "First Platypus Bank", Plaid's standard sandbox test institution
        initial_products=[Products("transactions")],
    )
    public_token = get_plaid_client().sandbox_public_token_create(sandbox_request).public_token

    item_id = None
    app.dependency_overrides[get_current_user_claims] = lambda: {"uid": test_uid, "email": "test@example.com"}
    try:
        client = TestClient(app)
        response = client.post("/bank-connection", json={"publicToken": public_token})
        assert response.status_code == 200
        assert response.json() == {"connectionStatus": "connected"}

        user = db.collection("users").document(test_uid).get().to_dict()
        item_id = user["plaidItemId"]
        assert user["connectionStatus"] == "connected"
        assert user["plaidAccessToken"]
        assert item_id

        enrollment = db.collection("enrollments").document(item_id).get()
        assert enrollment.exists
        assert enrollment.to_dict()["uid"] == test_uid

        # architecture.md §3.2: the initial sync may legitimately return no
        # data yet (Plaid Sandbox generates transaction history
        # asynchronously); §3.3.1's webhook-driven sync is what catches up.
        # Simulate that follow-up sync here with a bounded poll instead of
        # asserting synchronously on the initial connect response.
        accounts_ref = db.collection("users").document(test_uid).collection("accounts")
        accounts = list(accounts_ref.stream())
        for _ in range(5):
            if accounts:
                break
            time.sleep(3)
            sync_user_transactions(db, test_uid, refresh_all_account_balances=True)
            accounts = list(accounts_ref.stream())

        assert len(accounts) > 0
        for account in accounts:
            data = account.to_dict()
            assert data["type"] in ("checking", "credit_card")
            assert isinstance(data["balance"], (int, float))

        transactions = list(db.collection("users").document(test_uid).collection("transactions").stream())
        assert len(transactions) > 0
        for txn in transactions:
            data = txn.to_dict()
            assert data["status"] == "uncategorized"
            assert data["periodId"] == "period-1"
    finally:
        app.dependency_overrides.clear()
        _cleanup(db, test_uid, item_id=item_id)

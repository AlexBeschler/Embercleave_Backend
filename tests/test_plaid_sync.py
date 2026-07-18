from types import SimpleNamespace
from unittest.mock import patch

from app.services.plaid_sync import _map_account_type, sync_user_transactions


def _account(account_id, acct_type, name="Account", current=100.0, available=90.0):
    return SimpleNamespace(
        account_id=account_id,
        type=acct_type,
        name=name,
        balances=SimpleNamespace(current=current, available=available, last_updated_datetime=None),
    )


def _txn(
    transaction_id,
    account_id,
    amount=12.5,
    name="Coffee Shop",
    pending=False,
    pending_transaction_id=None,
):
    return SimpleNamespace(
        transaction_id=transaction_id,
        account_id=account_id,
        amount=amount,
        name=name,
        pending=pending,
        pending_transaction_id=pending_transaction_id,
        date=None,
        datetime=None,
        authorized_datetime=None,
    )


def _page(accounts=(), added=(), modified=(), removed=(), has_more=False, next_cursor="cursor-1"):
    return SimpleNamespace(
        accounts=list(accounts),
        added=list(added),
        modified=list(modified),
        removed=list(removed),
        has_more=has_more,
        next_cursor=next_cursor,
    )


def _seed_connected_user(db, uid, period_id="period-1"):
    db.collection("users").document(uid).set(
        {
            "email": "test@example.com",
            "connectionStatus": "connected",
            "plaidItemId": "item-1",
            "plaidAccessToken": "access-token-1",
            "plaidCursor": None,
            "activePeriodId": period_id,
        }
    )


def _cleanup(db, uid):
    user_ref = db.collection("users").document(uid)
    for sub in ("accounts", "transactions", "periods"):
        for doc in user_ref.collection(sub).stream():
            doc.reference.delete()
    user_ref.delete()


def test_map_account_type():
    assert _map_account_type(SimpleNamespace(type="depository")) == "checking"
    assert _map_account_type(SimpleNamespace(type="credit")) == "credit_card"
    assert _map_account_type(SimpleNamespace(type="investment")) is None
    assert _map_account_type(SimpleNamespace(type="loan")) is None


def test_sync_creates_account_and_transaction(db, test_uid):
    _seed_connected_user(db, test_uid)
    try:
        page = _page(
            accounts=[_account("acct-1", "depository")],
            added=[_txn("txn-1", "acct-1", amount=42.0, name="Groceries")],
        )
        with patch("app.services.plaid_sync.sync_transactions_page", return_value=page) as mock_sync:
            sync_user_transactions(db, test_uid, refresh_all_account_balances=False)
            mock_sync.assert_called_once_with("access-token-1", None)

        account = db.collection("users").document(test_uid).collection("accounts").document("acct-1").get()
        assert account.exists
        assert account.to_dict()["type"] == "checking"
        assert account.to_dict()["balance"] == 100.0

        txn = db.collection("users").document(test_uid).collection("transactions").document("txn-1").get()
        assert txn.exists
        data = txn.to_dict()
        assert data["accountType"] == "checking"
        assert data["amount"] == 42.0
        assert data["status"] == "uncategorized"
        assert data["budgetId"] is None
        assert data["periodId"] == "period-1"

        user = db.collection("users").document(test_uid).get().to_dict()
        assert user["plaidCursor"] == "cursor-1"
    finally:
        _cleanup(db, test_uid)


def test_sync_skips_user_not_connected(db, test_uid):
    db.collection("users").document(test_uid).set(
        {"connectionStatus": "not_connected", "activePeriodId": "period-1"}
    )
    try:
        with patch("app.services.plaid_sync.sync_transactions_page") as mock_sync:
            sync_user_transactions(db, test_uid, refresh_all_account_balances=False)
            mock_sync.assert_not_called()
    finally:
        _cleanup(db, test_uid)


def test_sync_filters_unsupported_account_types(db, test_uid):
    _seed_connected_user(db, test_uid)
    try:
        page = _page(
            accounts=[_account("acct-invest", "investment")],
            added=[_txn("txn-1", "acct-invest")],
        )
        with patch("app.services.plaid_sync.sync_transactions_page", return_value=page):
            sync_user_transactions(db, test_uid, refresh_all_account_balances=False)

        account = db.collection("users").document(test_uid).collection("accounts").document("acct-invest").get()
        assert not account.exists

        txn = db.collection("users").document(test_uid).collection("transactions").document("txn-1").get()
        assert not txn.exists
    finally:
        _cleanup(db, test_uid)


def test_sync_pending_to_posted_carries_forward_status_and_budget(db, test_uid):
    _seed_connected_user(db, test_uid)
    try:
        transactions_ref = db.collection("users").document(test_uid).collection("transactions")
        transactions_ref.document("pending-1").set(
            {
                "accountId": "acct-1",
                "accountType": "checking",
                "description": "Coffee",
                "amount": 5.0,
                "pending": True,
                "status": "accepted",
                "budgetId": "budget-1",
                "periodId": "period-1",
            }
        )

        page = _page(
            accounts=[_account("acct-1", "depository")],
            added=[_txn("posted-1", "acct-1", amount=5.0, pending_transaction_id="pending-1")],
            removed=[SimpleNamespace(transaction_id="pending-1", account_id="acct-1")],
        )
        with patch("app.services.plaid_sync.sync_transactions_page", return_value=page):
            sync_user_transactions(db, test_uid, refresh_all_account_balances=False)

        assert not transactions_ref.document("pending-1").get().exists
        posted = transactions_ref.document("posted-1").get().to_dict()
        assert posted["status"] == "accepted"
        assert posted["budgetId"] == "budget-1"
    finally:
        _cleanup(db, test_uid)


def test_sync_removed_without_match_is_just_deleted(db, test_uid):
    _seed_connected_user(db, test_uid)
    try:
        transactions_ref = db.collection("users").document(test_uid).collection("transactions")
        transactions_ref.document("gone-1").set(
            {"accountId": "acct-1", "accountType": "checking", "amount": 5.0, "status": "uncategorized"}
        )

        page = _page(removed=[SimpleNamespace(transaction_id="gone-1", account_id="acct-1")])
        with patch("app.services.plaid_sync.sync_transactions_page", return_value=page):
            sync_user_transactions(db, test_uid, refresh_all_account_balances=False)

        assert not transactions_ref.document("gone-1").get().exists
    finally:
        _cleanup(db, test_uid)


def test_sync_modified_never_overwrites_status_or_budget(db, test_uid):
    _seed_connected_user(db, test_uid)
    try:
        transactions_ref = db.collection("users").document(test_uid).collection("transactions")
        transactions_ref.document("txn-1").set(
            {
                "accountId": "acct-1",
                "accountType": "checking",
                "description": "Old name",
                "amount": 10.0,
                "pending": True,
                "status": "rejected",
                "budgetId": None,
                "periodId": "period-1",
            }
        )

        page = _page(
            accounts=[_account("acct-1", "depository")],
            modified=[_txn("txn-1", "acct-1", amount=10.0, pending=False)],
        )
        with patch("app.services.plaid_sync.sync_transactions_page", return_value=page):
            sync_user_transactions(db, test_uid, refresh_all_account_balances=False)

        data = transactions_ref.document("txn-1").get().to_dict()
        assert data["status"] == "rejected"
        assert data["budgetId"] is None
        assert data["pending"] is False
    finally:
        _cleanup(db, test_uid)


def test_sync_refresh_all_account_balances_uses_accounts_get(db, test_uid):
    _seed_connected_user(db, test_uid)
    try:
        page = _page(accounts=[_account("acct-1", "depository")])
        refreshed_accounts = [_account("acct-1", "depository", current=250.0, available=200.0)]
        with (
            patch("app.services.plaid_sync.sync_transactions_page", return_value=page),
            patch("app.services.plaid_sync.get_accounts", return_value=refreshed_accounts) as mock_get_accounts,
        ):
            sync_user_transactions(db, test_uid, refresh_all_account_balances=True)
            mock_get_accounts.assert_called_once_with("access-token-1")

        account = db.collection("users").document(test_uid).collection("accounts").document("acct-1").get()
        assert account.to_dict()["balance"] == 250.0
    finally:
        _cleanup(db, test_uid)


def test_sync_paginates_and_defers_cursor_persistence(db, test_uid):
    _seed_connected_user(db, test_uid)
    try:
        page_1 = _page(
            accounts=[_account("acct-1", "depository")],
            added=[_txn("txn-1", "acct-1")],
            has_more=True,
            next_cursor="cursor-page-2",
        )
        page_2 = _page(
            accounts=[_account("acct-1", "depository")],
            added=[_txn("txn-2", "acct-1")],
            has_more=False,
            next_cursor="cursor-final",
        )
        with patch("app.services.plaid_sync.sync_transactions_page", side_effect=[page_1, page_2]) as mock_sync:
            sync_user_transactions(db, test_uid, refresh_all_account_balances=False)
            assert mock_sync.call_count == 2
            mock_sync.assert_any_call("access-token-1", None)
            mock_sync.assert_any_call("access-token-1", "cursor-page-2")

        transactions_ref = db.collection("users").document(test_uid).collection("transactions")
        assert transactions_ref.document("txn-1").get().exists
        assert transactions_ref.document("txn-2").get().exists

        user = db.collection("users").document(test_uid).get().to_dict()
        assert user["plaidCursor"] == "cursor-final"
    finally:
        _cleanup(db, test_uid)

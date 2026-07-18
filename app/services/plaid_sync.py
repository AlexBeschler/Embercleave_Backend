from datetime import date, datetime, timezone

from google.cloud import firestore

from app.plaid_client import get_accounts, sync_transactions_page


def _to_datetime(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _map_account_type(account) -> str | None:
    """architecture.md §4/§11: only "checking" | "credit_card" are modeled.
    Accounts of other Plaid types (investment, loan, other) aren't part of
    this product's scope and are skipped."""
    if account.type == "depository":
        return "checking"
    if account.type == "credit":
        return "credit_card"
    return None


def _upsert_accounts(accounts_ref: firestore.CollectionReference, accounts: list) -> None:
    for account in accounts:
        mapped_type = _map_account_type(account)
        if mapped_type is None:
            continue
        balances = account.balances
        accounts_ref.document(account.account_id).set(
            {
                "type": mapped_type,
                "name": account.name,
                "balance": balances.current,
                "availableBalance": balances.available,
                "balanceDate": _to_datetime(balances.last_updated_datetime) or firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )


def sync_user_transactions(db: firestore.Client, uid: str, *, refresh_all_account_balances: bool) -> None:
    """Shared sync engine, architecture.md §3.3.1.

    Two callers, matching the documented account-refresh strategy for each:
    - Initial sync on /bank-connection (§3.2): refresh_all_account_balances=False —
      account balances are taken from whatever /transactions/sync itself returns.
    - Webhook (§3.3.1) and scheduled reconciliation (§3.3.2), which share this
      one function per the doc ("shared internal function, two entry points"):
      refresh_all_account_balances=True — an explicit /accounts/get call refreshes
      every account's balance once per sync, since a sync page's embedded accounts
      may omit accounts with no transaction activity in the current cursor window.

    Skips users who aren't connected (§3.3.1/§3.3.2: "both skip users with
    connectionStatus != connected").
    """
    user_ref = db.collection("users").document(uid)
    user_snapshot = user_ref.get()
    if not user_snapshot.exists:
        return
    user_data = user_snapshot.to_dict()
    if user_data.get("connectionStatus") != "connected":
        return

    access_token = user_data["plaidAccessToken"]
    active_period_id = user_data["activePeriodId"]
    cursor = user_data.get("plaidCursor")

    accounts_ref = user_ref.collection("accounts")
    transactions_ref = user_ref.collection("transactions")

    has_more = True
    next_cursor = cursor
    while has_more:
        page = sync_transactions_page(access_token, next_cursor)
        accounts_by_id = {a.account_id: _map_account_type(a) for a in page.accounts}

        if not refresh_all_account_balances:
            _upsert_accounts(accounts_ref, page.accounts)

        # Critical correctness rule (architecture.md §3.3.1): a pending
        # transaction posting shows up as a `removed` (old id) + `added`
        # (new id, linked via pending_transaction_id) pair. Capture the
        # removed doc's status/budgetId before deleting it so it can be
        # carried onto the new doc, preserving the user's categorization.
        carry_forward = {}
        for removed in page.removed:
            doc_ref = transactions_ref.document(removed.transaction_id)
            existing = doc_ref.get()
            if existing.exists:
                data = existing.to_dict()
                carry_forward[removed.transaction_id] = {
                    "status": data.get("status", "uncategorized"),
                    "budgetId": data.get("budgetId"),
                }
            doc_ref.delete()

        for txn in list(page.added) + list(page.modified):
            account_type = accounts_by_id.get(txn.account_id)
            if account_type is None:
                continue

            doc_ref = transactions_ref.document(txn.transaction_id)
            existing = doc_ref.get()
            fields = {
                "accountId": txn.account_id,
                "accountType": account_type,
                "description": txn.name,
                "amount": txn.amount,
                "postedDate": None if txn.pending else _to_datetime(txn.date),
                "transactedAt": _to_datetime(txn.datetime) or _to_datetime(txn.authorized_datetime),
                "pending": txn.pending,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
            if existing.exists:
                # Never overwrite status/budgetId set by the app.
                doc_ref.set(fields, merge=True)
            else:
                carry = carry_forward.get(txn.pending_transaction_id) if txn.pending_transaction_id else None
                fields["status"] = carry["status"] if carry else "uncategorized"
                fields["budgetId"] = carry["budgetId"] if carry else None
                fields["periodId"] = active_period_id
                fields["createdAt"] = firestore.SERVER_TIMESTAMP
                doc_ref.set(fields)

        has_more = page.has_more
        next_cursor = page.next_cursor

    if refresh_all_account_balances:
        _upsert_accounts(accounts_ref, get_accounts(access_token))

    user_ref.update({"plaidCursor": next_cursor, "updatedAt": firestore.SERVER_TIMESTAMP})

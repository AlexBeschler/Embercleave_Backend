from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(title="Embercleave API")

# architecture.md §5.1: embercleave-api and embercleave-internal run the same
# image but expose disjoint route sets — SERVICE_ROLE (set per-service in
# iac/cloud_run.tf) selects which. This keeps /reconcile from being reachable,
# unauthenticated, on the public service, which has allUsers as invoker.
if get_settings().service_role == "internal":
    from app.routers import internal

    app.include_router(internal.router)
else:
    from app.routers import bank_connection, budgets, clear_month, dashboard, transactions, users, webhooks

    app.include_router(users.router)
    app.include_router(bank_connection.router)
    app.include_router(webhooks.router)
    app.include_router(budgets.router)
    app.include_router(transactions.router)
    app.include_router(dashboard.router)
    app.include_router(clear_month.router)

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud import firestore

from app.auth import get_current_uid
from app.errors import NotFoundError
from app.firestore_client import get_firestore_client
from app.models import BudgetResponse, CreateBudgetRequest, PatchBudgetRequest, ReorderBudgetsRequest
from app.services.budgets import create_budget, delete_budget, list_budgets, patch_budget, reorder_budgets

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetResponse])
def get_budgets(
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> list[BudgetResponse]:
    return [BudgetResponse(**b) for b in list_budgets(db, uid)]


@router.post("", response_model=BudgetResponse)
def post_budget(
    body: CreateBudgetRequest,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> BudgetResponse:
    return BudgetResponse(**create_budget(db, uid, body.name, body.amount))


@router.post("/reorder")
def post_reorder(
    body: ReorderBudgetsRequest,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> dict:
    try:
        reorder_budgets(db, uid, body.orderedIds)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more budget ids not found")
    return {"status": "ok"}


@router.patch("/{budget_id}", response_model=BudgetResponse)
def patch_budget_route(
    budget_id: str,
    body: PatchBudgetRequest,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> BudgetResponse:
    try:
        return BudgetResponse(**patch_budget(db, uid, budget_id, name=body.name, amount=body.amount))
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")


@router.delete("/{budget_id}")
def delete_budget_route(
    budget_id: str,
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> dict:
    try:
        delete_budget(db, uid, budget_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return {"status": "ok"}

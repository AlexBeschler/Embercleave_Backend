from fastapi import APIRouter, Depends
from google.cloud import firestore

from app.auth import get_current_uid
from app.firestore_client import get_firestore_client
from app.models import ClearMonthResponse
from app.services.clear_month import clear_month

router = APIRouter(tags=["clear-month"])


@router.post("/clear-month", response_model=ClearMonthResponse)
def post_clear_month(
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> ClearMonthResponse:
    return ClearMonthResponse(**clear_month(db, uid))

from fastapi import APIRouter, Depends
from google.cloud import firestore

from app.auth import get_current_uid
from app.firestore_client import get_firestore_client
from app.models import DashboardResponse
from app.services.dashboard import get_dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    uid: str = Depends(get_current_uid),
    db: firestore.Client = Depends(get_firestore_client),
) -> DashboardResponse:
    return DashboardResponse(**get_dashboard(db, uid))

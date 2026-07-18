from functools import lru_cache

from google.cloud import firestore

from app.config import get_settings


@lru_cache
def get_firestore_client() -> firestore.Client:
    settings = get_settings()
    return firestore.Client(
        project=settings.project_id,
        database=settings.firestore_database,
    )

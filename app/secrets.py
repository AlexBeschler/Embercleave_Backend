from functools import lru_cache

from google.cloud import secretmanager

from app.config import get_settings


@lru_cache
def _client() -> secretmanager.SecretManagerServiceClient:
    return secretmanager.SecretManagerServiceClient()


@lru_cache
def get_secret(secret_id: str) -> str:
    """Fetches the latest enabled version of a Secret Manager secret.
    Cached for the life of the process — secret versions are populated
    out-of-band (see iac/secrets.tf) and a new Cloud Run revision picks up
    any rotation on cold start.
    """
    settings = get_settings()
    name = f"projects/{settings.project_id}/secrets/{secret_id}/versions/latest"
    response = _client().access_secret_version(name=name)
    return response.payload.data.decode("utf-8")

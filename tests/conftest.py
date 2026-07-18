import uuid

import pytest

from app.config import get_settings
from app.firestore_client import get_firestore_client


@pytest.fixture(scope="session")
def db():
    settings = get_settings()
    assert settings.environment == "dev", "tests must run against the dev environment, never prod"
    return get_firestore_client()


@pytest.fixture
def test_uid():
    """A throwaway uid namespaced so it's obviously test data and never
    collides with a real user, against the real dev Firestore database.
    """
    return f"test-{uuid.uuid4()}"

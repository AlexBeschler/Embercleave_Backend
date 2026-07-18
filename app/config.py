import os
from functools import lru_cache


class Settings:
    """Env-driven settings. One container image runs against either the
    dev or prod environment depending on ENVIRONMENT — see architecture.md
    §5.1 (both Cloud Run services share one image; environment is config,
    not code).
    """

    def __init__(self) -> None:
        self.environment = os.environ.get("ENVIRONMENT", "dev")
        self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "embercleave-56804")
        self.firestore_database = f"embercleave-{self.environment}"
        # "public" (embercleave-api) or "internal" (embercleave-internal) —
        # controls which routers main.py registers, see iac/cloud_run.tf.
        self.service_role = os.environ.get("SERVICE_ROLE", "public")

        # Plaid: client_id is shared across environments, secret is
        # per-environment (dev holds the Sandbox secret, prod holds the
        # Production secret) — see architecture.md §5.4, iac/secrets.tf.
        self.plaid_env = "sandbox" if self.environment == "dev" else "production"
        self.plaid_client_id_secret_id = "embercleave-plaid-client-id"
        self.plaid_secret_secret_id = f"embercleave-plaid-secret-{self.environment}"


@lru_cache
def get_settings() -> Settings:
    return Settings()

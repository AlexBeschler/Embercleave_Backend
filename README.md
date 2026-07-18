# Embercleave Backend

Cloud Run service implementing [architecture.md](../architecture.md). One
container image (this repo) runs as both `embercleave-api-{env}` and
`embercleave-internal-{env}`. The two services differ in ingress/IAM
(§5.1) and in one deliberate, minimal code branch: `SERVICE_ROLE`
(`public` | `internal`, set per-service in `iac/cloud_run.tf`) selects
which routers `app/main.py` registers, so `/reconcile` isn't reachable
on the public, `allUsers`-invokable service — see the comment in
`app/main.py` for why.

## Local setup

```
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

Requires `gcloud auth application-default login` with access to the
`embercleave-56804` GCP project (Firestore, Firebase Auth, and Secret
Manager for the target environment).

On macOS you may also need `SSL_CERT_FILE=$(python3 -c "import certifi;
print(certifi.where())")` exported for outbound HTTPS calls to Plaid to
pass certificate verification — Python's default SSL context doesn't
always pick up the system/Homebrew CA bundle.

## Running locally

```
GOOGLE_CLOUD_PROJECT=embercleave-56804 ENVIRONMENT=dev SERVICE_ROLE=public \
  .venv/bin/uvicorn app.main:app --reload --port 8080
```

`ENVIRONMENT` selects the Firestore database (`embercleave-{env}`, per
`iac/firestore.tf`) and which Plaid secret is loaded (`embercleave-plaid-secret-{env}`,
dev = Sandbox, prod = Production, per `iac/secrets.tf`); it does not affect
which GCP project is used, since Firebase Auth is a single shared project
across environments (see `iac/firebase.tf`). Set `SERVICE_ROLE=internal` to
run the `/reconcile`-only surface instead (what `embercleave-internal` runs).

## Tests

```
GOOGLE_CLOUD_PROJECT=embercleave-56804 ENVIRONMENT=dev .venv/bin/pytest
```

Tests run against the real `embercleave-dev` Firestore database via
Application Default Credentials (no emulator, no mocked Firestore) and
clean up their own test documents (uid-prefixed `test-<uuid>`). They must
never be pointed at `ENVIRONMENT=prod` — `tests/conftest.py` asserts this.

The Plaid HTTP layer (`app/plaid_client.py`) is stubbed in these tests —
`embercleave-plaid-secret-dev` doesn't yet hold a real Plaid Sandbox
secret, so there's no live Plaid API to test against. Everything else is
real: Firestore reads/writes, and the webhook JWT verification tests sign
real ES256 tokens with a locally generated EC keypair and verify them with
the actual `app/plaid_webhook_verify.py` logic. Once a real Sandbox secret
is populated, add an end-to-end test using Plaid's `/sandbox/public_token/create`
to drive a real `/bank-connection` round trip.

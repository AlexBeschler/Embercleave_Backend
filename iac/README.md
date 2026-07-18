# Embercleave Terraform

Implements the infrastructure in [architecture.md](../architecture.md): one
GCP project (`embercleave-56804`), shared by two environments (`dev`,
`prod`) via resource-name suffixes and, for Firestore, named databases.
Firebase Authentication is a single shared user pool across both
environments — see the note at the top of `firebase.tf`.

## First-time setup

1. **Bootstrap** (creates the project and the remote-state bucket; this
   config keeps its own local state since it changes rarely):
   ```
   cd bootstrap
   terraform init
   terraform apply
   ```
2. **Point the main config at the new state bucket**, then apply:
   ```
   cd ..
   terraform init -backend-config="bucket=$(terraform -chdir=bootstrap output -raw state_bucket)" -backend-config="prefix=embercleave"
   terraform apply
   ```

## Populating secrets

Terraform only creates the Secret Manager *containers* (`secrets.tf`) —
never a version, so the Plaid client ID/secret never touch Terraform state.
Add the actual values after apply:

```
echo -n "<your Plaid client_id>" | gcloud secrets versions add embercleave-plaid-client-id --data-file=-
echo -n "<your Plaid Sandbox secret>" | gcloud secrets versions add embercleave-plaid-secret-dev --data-file=-
echo -n "<your Plaid Production secret>" | gcloud secrets versions add embercleave-plaid-secret-prod --data-file=-
```

`client_id` is shared across Plaid environments (one secret); `secret` is
per-environment — dev holds the Sandbox secret, prod holds the Production
secret.

## Deploying the app image

Both `embercleave-api-<env>` and `embercleave-internal-<env>` start out
pointed at a placeholder image (`gcr.io/cloudrun/hello`). Terraform is
configured to ignore drift on the deployed image (see `cloud_run.tf`), so
CI is expected to push new revisions directly, e.g.:

```
gcloud run deploy embercleave-api-prod --image <artifact-registry-image> --region us-central1
gcloud run deploy embercleave-internal-prod --image <artifact-registry-image> --region us-central1
```

Images should be pushed to the Artifact Registry repo this config creates
(`artifact_registry_repository` output).

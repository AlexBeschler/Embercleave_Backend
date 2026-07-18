# Secret containers only — Terraform never sets secret_manager_secret_version
# values, so the actual Plaid client_id/secret material never touches
# Terraform state. Populate versions out-of-band, e.g.:
#   gcloud secrets versions add embercleave-plaid-client-id --data-file=-
#   gcloud secrets versions add embercleave-plaid-secret-prod --data-file=-

# client_id is shared across Plaid's Sandbox/Production environments, so
# unlike plaid_secret this is a single secret, not one per environment.
resource "google_secret_manager_secret" "plaid_client_id" {
  project   = data.google_project.this.project_id
  secret_id = "embercleave-plaid-client-id"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "plaid_client_id_access" {
  for_each = toset(local.environments)

  project   = data.google_project.this.project_id
  secret_id = google_secret_manager_secret.plaid_client_id.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run[each.value].email}"
}

# One secret per environment: dev holds the Plaid Sandbox secret, prod holds
# the Plaid Production secret.
resource "google_secret_manager_secret" "plaid_secret" {
  for_each = toset(local.environments)

  project   = data.google_project.this.project_id
  secret_id = "embercleave-plaid-secret-${each.value}"

  labels = {
    environment = each.value
  }

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "plaid_secret_access" {
  for_each = toset(local.environments)

  project   = data.google_project.this.project_id
  secret_id = google_secret_manager_secret.plaid_secret[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run[each.value].email}"
}

# Named databases (not "(default)") so dev and prod data live in the same
# project without mixing. IAM for Firestore access stays at the project
# level (see service_accounts.tf) — isolation between dev/prod data relies
# on each Cloud Run revision only ever being configured to target its own
# database ID, the same app-code-is-the-boundary trust model architecture.md
# already uses for Firestore access control generally (§5.2).
resource "google_firestore_database" "this" {
  for_each = toset(local.environments)

  project     = data.google_project.this.project_id
  name        = "embercleave-${each.value}"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

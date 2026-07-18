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

# Security Rules (architecture.md §5.2): deny all direct client access,
# defense-in-depth since every real read/write already goes through Cloud
# Run's Admin SDK. One ruleset, released against each named database (rules
# releases for non-default Firestore databases are addressed as
# "cloud.firestore/{database}").
resource "google_firebaserules_ruleset" "firestore" {
  project = data.google_project.this.project_id

  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/firestore.rules")
    }
  }

  depends_on = [google_firebase_project.default]
}

resource "google_firebaserules_release" "firestore" {
  for_each = toset(local.environments)

  project      = data.google_project.this.project_id
  name         = "cloud.firestore/${google_firestore_database.this[each.value].name}"
  ruleset_name = "projects/${data.google_project.this.project_id}/rulesets/${google_firebaserules_ruleset.firestore.name}"

  depends_on = [google_firestore_database.this]
}

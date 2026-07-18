# Per architecture.md §5.1: both Cloud Run services in an environment share
# one dedicated runtime identity; Cloud Scheduler gets its own, separate
# identity that can only invoke Cloud Run.

resource "google_service_account" "cloud_run" {
  for_each = toset(local.environments)

  project      = data.google_project.this.project_id
  account_id   = "embercleave-run-${each.value}"
  display_name = "Embercleave Cloud Run runtime (${each.value})"
}

resource "google_project_iam_member" "cloud_run_datastore" {
  for_each = toset(local.environments)

  project = data.google_project.this.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run[each.value].email}"
}

resource "google_service_account" "scheduler" {
  for_each = toset(local.environments)

  project      = data.google_project.this.project_id
  account_id   = "embercleave-sched-${each.value}"
  display_name = "Embercleave Cloud Scheduler invoker (${each.value})"
}

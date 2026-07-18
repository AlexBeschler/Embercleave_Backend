# Safety-net sync (architecture.md §3.3.2) — one job per environment,
# OIDC-authenticated as that environment's scheduler service account,
# targeting that environment's private embercleave-internal service.
resource "google_cloud_scheduler_job" "reconcile" {
  for_each = toset(local.environments)

  project   = data.google_project.this.project_id
  region    = var.region
  name      = "embercleave-reconcile-${each.value}"
  schedule  = var.reconciliation_schedule
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.internal[each.value].uri}/reconcile"

    oidc_token {
      service_account_email = google_service_account.scheduler[each.value].email
      audience              = google_cloud_run_v2_service.internal[each.value].uri
    }
  }

  retry_config {
    retry_count = 3
  }

  depends_on = [google_project_service.apis]
}

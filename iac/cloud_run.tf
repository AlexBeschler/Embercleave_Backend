# Same container image on both services (architecture.md §5.1); they differ
# only in ingress/IAM. `ingress` is ALL on both — "private" for the internal
# service means IAM-invoker-restricted, not network-restricted, since Cloud
# Scheduler calls it over its public URL with an OIDC token.
#
# image is set once here; CI updates the running revision out-of-band
# (`gcloud run deploy` / a new revision), so Terraform is told to ignore
# drift on it rather than reverting to the placeholder on every apply.

resource "google_cloud_run_v2_service" "api" {
  for_each = toset(local.environments)

  project  = data.google_project.this.project_id
  name     = "embercleave-api-${each.value}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run[each.value].email

    containers {
      image = var.container_image[each.value]

      env {
        name  = "ENVIRONMENT"
        value = each.value
      }

      env {
        name  = "SERVICE_ROLE"
        value = "public"
      }
    }
  }

  # Scale-to-zero (architecture.md §5.1); declared explicitly so Terraform
  # doesn't perpetually diff against GCP's own default-populated block.
  scaling {
    manual_instance_count = 0
    min_instance_count    = 0
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [google_project_service.apis]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  for_each = toset(local.environments)

  project  = data.google_project.this.project_id
  location = var.region
  name     = google_cloud_run_v2_service.api[each.value].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service" "internal" {
  for_each = toset(local.environments)

  project  = data.google_project.this.project_id
  name     = "embercleave-internal-${each.value}"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.cloud_run[each.value].email

    containers {
      image = var.container_image[each.value]

      env {
        name  = "ENVIRONMENT"
        value = each.value
      }

      env {
        name  = "SERVICE_ROLE"
        value = "internal"
      }
    }
  }

  # Scale-to-zero (architecture.md §5.1); declared explicitly so Terraform
  # doesn't perpetually diff against GCP's own default-populated block.
  scaling {
    manual_instance_count = 0
    min_instance_count    = 0
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [google_project_service.apis]
}

# No allUsers binding here — only the scheduler SA (per environment) can
# invoke this service, enforced by Cloud Run's platform-level IAM check.
resource "google_cloud_run_v2_service_iam_member" "internal_scheduler" {
  for_each = toset(local.environments)

  project  = data.google_project.this.project_id
  location = var.region
  name     = google_cloud_run_v2_service.internal[each.value].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler[each.value].email}"
}

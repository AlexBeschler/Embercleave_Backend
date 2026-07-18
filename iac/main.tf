locals {
  environments = ["dev", "prod"]

  apis = [
    "firebase.googleapis.com",
    "identitytoolkit.googleapis.com",
    "run.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "cloudbuild.googleapis.com",
  ]
}

# The project itself is created by ../bootstrap, not here — this config's
# own remote state lives in a bucket that has to exist before this config
# can run, so project creation can't happen in the same config.
data "google_project" "this" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each = toset(local.apis)
  project  = data.google_project.this.project_id
  service  = each.value
}

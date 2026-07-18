terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Creates the GCP project itself and the GCS bucket that holds the main
# config's remote state. Both have to exist before the main config's "gcs"
# backend can be initialized, so this lives in a separate, local-state
# config that's applied once and touched rarely thereafter.
resource "google_project" "this" {
  name            = var.project_id
  project_id      = var.project_id
  billing_account = var.billing_account_id
}

resource "google_project_service" "storage" {
  project = google_project.this.project_id
  service = "storage.googleapis.com"
}

resource "google_storage_bucket" "terraform_state" {
  name                        = "${var.project_id}-tfstate"
  project                     = google_project.this.project_id
  location                    = var.region
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  depends_on = [google_project_service.storage]
}

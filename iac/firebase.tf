# Firebase Authentication is shared across dev and prod (one Firebase
# project, one user pool) — see terraform/README.md for the tradeoff this
# implies. Everything else (Firestore, Cloud Run, secrets) is split per
# environment.

resource "google_firebase_project" "default" {
  provider = google-beta
  project  = data.google_project.this.project_id

  depends_on = [google_project_service.apis]
}

resource "google_firebase_apple_app" "ios" {
  provider     = google-beta
  project      = data.google_project.this.project_id
  display_name = "Embercleave iOS"
  bundle_id    = var.ios_bundle_id

  depends_on = [google_firebase_project.default]
}

resource "google_firebase_android_app" "android" {
  provider     = google-beta
  project      = data.google_project.this.project_id
  display_name = "Embercleave Android"
  package_name = var.android_package_name

  depends_on = [google_firebase_project.default]
}

# Default Hosting site, at <project_id>.web.app — exists solely to serve the
# static apple-app-site-association file Plaid's OAuth bank-redirect flow
# needs for the iOS Associated Domains / Universal Links handoff. Terraform
# only declares the site; its content is deployed out-of-band via the
# Firebase CLI (same reasoning as cloud_run.tf's ignore_changes on image —
# Terraform shouldn't fight a deploy flow it doesn't drive).
resource "google_firebase_hosting_site" "default" {
  provider = google-beta
  project  = data.google_project.this.project_id
  site_id  = data.google_project.this.project_id

  depends_on = [google_firebase_project.default]
}

# Enables Firebase Authentication itself (Identity Platform config) with
# email/password sign-in. Chosen over Google/Apple sign-in for v1 because
# those require a manually-created OAuth client in GCP Console first (no
# Terraform resource can create one) — email/password is fully
# self-provisioning. architecture.md §5.3 leaves the sign-in method open;
# this is the decision.
resource "google_identity_platform_config" "default" {
  project = data.google_project.this.project_id

  sign_in {
    email {
      enabled           = true
      password_required = true
    }

    phone_number {
      enabled = false
    }
  }

  # No multi-tenancy needed (§5.3 — single user pool shared across
  # dev/prod); declared explicitly so Terraform doesn't perpetually diff
  # against GCP's own default-populated block.
  multi_tenant {
    allow_tenants = false
  }

  depends_on = [google_firebase_project.default]
}

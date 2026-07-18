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

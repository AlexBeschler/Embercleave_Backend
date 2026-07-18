# One shared repo for both environments; dev/prod images are distinguished
# by tag, not by repo.
resource "google_artifact_registry_repository" "images" {
  project       = data.google_project.this.project_id
  location      = var.region
  repository_id = "embercleave"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

output "project_id" {
  value = google_project.this.project_id
}

output "state_bucket" {
  value = google_storage_bucket.terraform_state.name
}

output "project_id" {
  value = data.google_project.this.project_id
}

output "cloud_run_api_urls" {
  value = { for env, svc in google_cloud_run_v2_service.api : env => svc.uri }
}

output "cloud_run_internal_urls" {
  value = { for env, svc in google_cloud_run_v2_service.internal : env => svc.uri }
}

output "cloud_run_service_account_emails" {
  value = { for env, sa in google_service_account.cloud_run : env => sa.email }
}

output "scheduler_service_account_emails" {
  value = { for env, sa in google_service_account.scheduler : env => sa.email }
}

output "firestore_database_names" {
  value = { for env, db in google_firestore_database.this : env => db.name }
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.images.id
}

output "plaid_client_id_secret_id" {
  value = google_secret_manager_secret.plaid_client_id.secret_id
}

output "plaid_secret_ids" {
  value = { for env, secret in google_secret_manager_secret.plaid_secret : env => secret.secret_id }
}

output "firebase_ios_app_id" {
  value = google_firebase_apple_app.ios.app_id
}

output "firebase_android_app_id" {
  value = google_firebase_android_app.android.app_id
}

output "hosting_default_url" {
  value = google_firebase_hosting_site.default.default_url
}

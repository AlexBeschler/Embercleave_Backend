variable "project_id" {
  description = "GCP project ID (created by ../bootstrap)"
  type        = string
}

variable "region" {
  description = "GCP region for all resources"
  type        = string
  default     = "us-central1"
}

variable "ios_bundle_id" {
  description = "iOS bundle identifier registered with Firebase"
  type        = string
  default     = "dev.layer12.project-embercleave"
}

variable "android_package_name" {
  description = "Android application ID registered with Firebase"
  type        = string
  default     = "dev.layer12.Embercleave"
}

variable "container_image" {
  description = "Container image deployed to both Cloud Run services, per environment. Terraform only sets the initial image; CI updates it out-of-band (see the ignore_changes lifecycle block on the Cloud Run services)."
  type        = map(string)
  default = {
    dev  = "gcr.io/cloudrun/hello"
    prod = "gcr.io/cloudrun/hello"
  }
}

variable "reconciliation_schedule" {
  description = "Cron schedule (Cloud Scheduler syntax) for the daily reconciliation job, same for both environments"
  type        = string
  default     = "0 6 * * *"
}

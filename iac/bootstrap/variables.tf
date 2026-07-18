variable "project_id" {
  description = "GCP project ID to create"
  type        = string
}

variable "billing_account_id" {
  description = "Billing account to link the new project to"
  type        = string
}

variable "region" {
  description = "Region for the Terraform state bucket"
  type        = string
  default     = "us-central1"
}

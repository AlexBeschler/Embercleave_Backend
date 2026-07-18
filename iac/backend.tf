terraform {
  # Bucket comes from ../bootstrap's output (state_bucket). Configure with:
  #   terraform init -backend-config="bucket=<state_bucket>" -backend-config="prefix=embercleave"
  backend "gcs" {}
}

# =============================================================================
# Object Storage Bucket per Velero Backup (free tier: 20 GB Standard)
# =============================================================================

resource "oci_objectstorage_bucket" "velero" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.ns.namespace
  name           = var.velero_bucket_name
  access_type    = "NoPublicAccess"
  storage_tier   = "Standard"

  versioning = "Disabled"

  freeform_tags = {
    "Purpose"   = "velero-backup"
    "ManagedBy" = "terraform"
  }
}

# Customer Secret Key per accesso S3-compatible (usata da Velero)
resource "oci_identity_customer_secret_key" "velero" {
  display_name = "velero-s3-key"
  user_id      = var.user_ocid
}

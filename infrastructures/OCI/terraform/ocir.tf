# =============================================================================
# OCIR - Oracle Container Image Registry (gratuito)
# =============================================================================
# OCIR e' incluso gratuitamente in OCI. Lo storage delle immagini usa
# Object Storage (free tier: 20 GB condivisi con altri bucket).
#
# Endpoint: <region>.ocir.io  (es: eu-milan-1.ocir.io)
# Full image path: <region>.ocir.io/<namespace>/<repo-name>:<tag>
# Login: <namespace>/<username> con Auth Token come password
# =============================================================================

# Configurazione OCIR a livello tenancy
# - Abilita creazione automatica repo al primo push
resource "oci_artifacts_container_configuration" "ocir_config" {
  compartment_id                      = var.tenancy_ocid
  is_repository_created_on_first_push = true
}

# Repository per le immagini Docker dei microservizi
resource "oci_artifacts_container_repository" "repos" {
  for_each = toset(var.ocir_repositories)

  compartment_id = var.compartment_ocid
  display_name   = each.value
  is_public      = false
  is_immutable   = false

  readme {
    content = "Managed by Terraform"
    format  = "text/plain"
  }
}

# Auth Token per docker login / imagePullSecret K8s
# OCI ha un limite di 2 auth token per utente. Se la quota e' piena,
# imposta create_ocir_auth_token = false in terraform.tfvars e usa un token esistente.
resource "oci_identity_auth_token" "ocir" {
  count       = var.create_ocir_auth_token ? 1 : 0
  description = "ocir-docker-login"
  user_id     = var.user_ocid
}

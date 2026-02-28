# =============================================================================
# Data Sources
# =============================================================================

# Availability Domain
data "oci_identity_availability_domain" "ad" {
  compartment_id = var.tenancy_ocid
  ad_number      = 1
}

# Ultima versione Kubernetes disponibile su OKE
data "oci_containerengine_cluster_option" "oke" {
  cluster_option_id = "all"
}

locals {
  # Usa la versione specificata o l'ultima disponibile
  k8s_version = var.kubernetes_version != null ? var.kubernetes_version : (
    reverse(sort(data.oci_containerengine_cluster_option.oke.kubernetes_versions))[0]
  )
}

# Immagini disponibili per i node pool OKE
data "oci_containerengine_node_pool_option" "oke" {
  node_pool_option_id = "all"
}

locals {
  # Filtra: OKE ARM64 images per la versione K8s scelta, Oracle Linux 8
  oke_arm64_images = [
    for s in data.oci_containerengine_node_pool_option.oke.sources :
    s if can(regex("Oracle-Linux-8.*aarch64.*OKE", s.source_name))
  ]
  # Prendi la prima (più recente)
  oke_arm64_image_id = local.oke_arm64_images[0].image_id
}

# Immagine per micro VM AMD (E2.1.Micro)
data "oci_core_images" "micro_amd64" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Oracle Linux"
  operating_system_version = "8"
  shape                    = "VM.Standard.E2.1.Micro"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

# OCI Services (per Service Gateway - accesso OCIR gratuito)
data "oci_core_services" "all" {
}

# Object Storage Namespace (necessario per S3-compatible endpoint)
data "oci_objectstorage_namespace" "ns" {
  compartment_id = var.tenancy_ocid
}

locals {
  # Service per Object Storage / OCIR
  oci_services_id   = [for s in data.oci_core_services.all.services : s.id if can(regex("all-.*-services-in-oracle-services-network", s.cidr_block))][0]
  oci_services_cidr = [for s in data.oci_core_services.all.services : s.cidr_block if can(regex("all-.*-services-in-oracle-services-network", s.cidr_block))][0]

  # S3-compatible endpoint per Velero
  s3_endpoint = "https://${data.oci_objectstorage_namespace.ns.namespace}.compat.objectstorage.${var.region}.oraclecloud.com"
}

# =============================================================================
# OCI Authentication
# =============================================================================

variable "tenancy_ocid" {
  description = "OCID del tenancy OCI"
  type        = string
}

variable "user_ocid" {
  description = "OCID dell'utente OCI"
  type        = string
}

variable "fingerprint" {
  description = "Fingerprint della API key OCI"
  type        = string
}

variable "private_key_path" {
  description = "Path alla chiave privata OCI API"
  type        = string
}

variable "region" {
  description = "Regione OCI"
  type        = string
  default     = "eu-milan-1"
}

variable "compartment_ocid" {
  description = "OCID del compartment"
  type        = string
}

variable "ssh_public_key" {
  description = "Chiave pubblica SSH per accesso ai nodi"
  type        = string
}

# =============================================================================
# OKE Cluster
# =============================================================================

variable "cluster_name" {
  description = "Nome del cluster OKE"
  type        = string
  default     = "events-oke"
}

variable "kubernetes_version" {
  description = "Versione di Kubernetes (null = ultima disponibile)"
  type        = string
  default     = null
}

# =============================================================================
# Network
# =============================================================================

variable "vcn_cidr" {
  description = "CIDR block della VCN"
  type        = string
  default     = "10.0.0.0/16"
}

# =============================================================================
# Node Pool - Heavy (ARM64 A1.Flex)
# =============================================================================

variable "heavy_pool_ocpus" {
  description = "OCPU per il nodo heavy"
  type        = number
  default     = 3
}

variable "heavy_pool_memory_gb" {
  description = "GB di RAM per il nodo heavy"
  type        = number
  default     = 18
}

variable "heavy_pool_boot_volume_gb" {
  description = "GB boot volume per il nodo heavy"
  type        = number
  default     = 120
}

variable "heavy_pool_size" {
  description = "Numero di nodi nel pool heavy"
  type        = number
  default     = 1
}

# =============================================================================
# Node Pool - Light (ARM64 A1.Flex)
# =============================================================================

variable "light_pool_ocpus" {
  description = "OCPU per il nodo light"
  type        = number
  default     = 1
}

variable "light_pool_memory_gb" {
  description = "GB di RAM per il nodo light"
  type        = number
  default     = 6
}

variable "light_pool_boot_volume_gb" {
  description = "GB boot volume per il nodo light"
  type        = number
  default     = 40
}

variable "light_pool_size" {
  description = "Numero di nodi nel pool light"
  type        = number
  default     = 1
}

# =============================================================================
# Micro VMs (AMD E2.1.Micro - standalone, fuori dal cluster)
# =============================================================================

variable "micro_vm_count" {
  description = "Numero di VM micro E2.1.Micro (max 2 free tier)"
  type        = number
  default     = 2
}

variable "micro_vm_boot_volume_gb" {
  description = "GB boot volume per le micro VM (minimo OCI: 50)"
  type        = number
  default     = 50

  validation {
    condition     = var.micro_vm_boot_volume_gb >= 50
    error_message = "Il boot volume minimo OCI e' 50 GB."
  }
}

# =============================================================================
# Object Storage (per Velero backup, free tier: 20 GB Standard)
# =============================================================================

variable "velero_bucket_name" {
  description = "Nome del bucket Object Storage per Velero"
  type        = string
  default     = "velero-backups"
}

# =============================================================================
# OCIR (Oracle Container Image Registry, gratuito)
# =============================================================================

variable "ocir_repositories" {
  description = "Lista di repository OCIR da creare"
  type        = list(string)
  default     = ["events/backoffice", "events/scraping"]
}

variable "ocir_email" {
  description = "Email per OCIR username (formato: namespace/email)"
  type        = string
}

variable "create_ocir_auth_token" {
  description = "Crea un nuovo Auth Token per OCIR. Disattivare se la quota di 2 token e' gia' raggiunta."
  type        = bool
  default     = true
}

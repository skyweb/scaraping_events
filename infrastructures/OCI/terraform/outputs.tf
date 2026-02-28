# =============================================================================
# OKE Cluster
# =============================================================================

output "cluster_id" {
  description = "OCID del cluster OKE"
  value       = oci_containerengine_cluster.oke.id
}

output "cluster_endpoint" {
  description = "Endpoint del K8s API server"
  value       = oci_containerengine_cluster.oke.endpoints[0].public_endpoint
}

output "cluster_name" {
  description = "Nome del cluster OKE"
  value       = oci_containerengine_cluster.oke.name
}

output "kubernetes_version" {
  description = "Versione Kubernetes"
  value       = local.k8s_version
}

output "kubeconfig_command" {
  description = "Comando per ottenere il kubeconfig"
  value       = "oci ce cluster create-kubeconfig --cluster-id ${oci_containerengine_cluster.oke.id} --file $HOME/.kube/config --region ${var.region} --token-version 2.0.0 --kube-endpoint PUBLIC_ENDPOINT"
}

# =============================================================================
# Node Pools
# =============================================================================

output "heavy_pool_id" {
  description = "OCID del node pool heavy"
  value       = oci_containerengine_node_pool.heavy.id
}

output "light_pool_id" {
  description = "OCID del node pool light"
  value       = oci_containerengine_node_pool.light.id
}

# =============================================================================
# Network
# =============================================================================

output "vcn_id" {
  description = "OCID della VCN"
  value       = oci_core_vcn.oke_vcn.id
}

output "api_subnet_id" {
  description = "OCID della subnet API endpoint"
  value       = oci_core_subnet.api_subnet.id
}

output "node_subnet_id" {
  description = "OCID della subnet nodi"
  value       = oci_core_subnet.node_subnet.id
}

output "lb_subnet_id" {
  description = "OCID della subnet load balancer"
  value       = oci_core_subnet.lb_subnet.id
}

# =============================================================================
# Micro VMs
# =============================================================================

output "micro_vm_public_ips" {
  description = "IP pubblici delle micro VM"
  value       = oci_core_instance.micro_vm[*].public_ip
}

output "micro_vm_private_ips" {
  description = "IP privati delle micro VM"
  value       = oci_core_instance.micro_vm[*].private_ip
}

output "micro_vm_names" {
  description = "Nomi delle micro VM"
  value       = oci_core_instance.micro_vm[*].display_name
}

output "ssh_micro_commands" {
  description = "Comandi SSH per le micro VM"
  value = [
    for vm in oci_core_instance.micro_vm :
    "ssh opc@${vm.public_ip}  # ${vm.display_name}"
  ]
}

# =============================================================================
# IAM (Instance Principal - Grafana OCI Monitoring)
# =============================================================================

output "grafana_dynamic_group" {
  description = "Dynamic Group per Instance Principal Grafana"
  value       = oci_identity_dynamic_group.micro_monitor.name
}

output "grafana_iam_policy" {
  description = "IAM Policy per Grafana OCI Monitoring"
  value       = oci_identity_policy.grafana_monitoring.name
}

# =============================================================================
# Object Storage (Velero)
# =============================================================================

output "velero_bucket_name" {
  description = "Nome del bucket Object Storage per Velero"
  value       = oci_objectstorage_bucket.velero.name
}

output "velero_s3_endpoint" {
  description = "Endpoint S3-compatible per Velero"
  value       = local.s3_endpoint
}

output "velero_s3_access_key" {
  description = "Access Key ID per Velero (Customer Secret Key)"
  value       = oci_identity_customer_secret_key.velero.id
}

output "velero_s3_secret_key" {
  description = "Secret Access Key per Velero"
  value       = oci_identity_customer_secret_key.velero.key
  sensitive   = true
}

output "objectstorage_namespace" {
  description = "Object Storage Namespace"
  value       = data.oci_objectstorage_namespace.ns.namespace
}

# =============================================================================
# OCIR (Oracle Container Image Registry)
# =============================================================================

output "ocir_endpoint" {
  description = "Endpoint OCIR (docker login)"
  value       = "${var.region}.ocir.io"
}

output "ocir_docker_server" {
  description = "Docker server OCIR completo con namespace"
  value       = "${var.region}.ocir.io/${data.oci_objectstorage_namespace.ns.namespace}"
}

output "ocir_auth_token" {
  description = "Auth Token per docker login OCIR"
  value       = oci_identity_auth_token.ocir.token
  sensitive   = true
}

output "region" {
  description = "Regione OCI"
  value       = var.region
}

output "tenancy_ocid" {
  description = "OCID del tenancy OCI"
  value       = var.tenancy_ocid
  sensitive   = true
}

output "ocir_username" {
  description = "Username OCIR (namespace/email)"
  value       = "${data.oci_objectstorage_namespace.ns.namespace}/${var.ocir_email}"
}

output "ocir_repositories" {
  description = "Repository OCIR creati"
  value = {
    for k, v in oci_artifacts_container_repository.repos :
    k => "${var.region}.ocir.io/${data.oci_objectstorage_namespace.ns.namespace}/${v.display_name}"
  }
}

# =============================================================================
# IAM - Instance Principal per Grafana (OCI Monitoring)
# =============================================================================
# Permette alla micro-monitor VM di leggere metriche OCI Monitoring
# senza chiavi API, usando Instance Principal.
#
# Metriche disponibili via OCI Monitoring:
#   - CpuUtilization, MemoryUtilization (compute)
#   - NetworkBytesIn/Out, NetworkPacketsIn/Out (VCN)
#   - DiskBytesRead/Written, DiskIopsRead/Written (block storage)
#   - oci_computeagent (host-level metrics)
#   - oci_vcn (VCN flow metrics)
#   - oci_oke (cluster metrics)
# =============================================================================

# Dynamic Group: matcha la micro-monitor VM (indice 0)
resource "oci_identity_dynamic_group" "micro_monitor" {
  compartment_id = var.tenancy_ocid
  name           = "grafana-monitor-dg"
  description    = "Micro-monitor VM - Grafana Instance Principal for OCI Monitoring"
  matching_rule  = "instance.id = '${oci_core_instance.micro_vm[0].id}'"
}

# IAM Policy: permette lettura metriche, istanze, VCN, OKE
resource "oci_identity_policy" "grafana_monitoring" {
  compartment_id = var.tenancy_ocid
  name           = "grafana-oci-monitoring"
  description    = "Allow Grafana on micro-monitor to read OCI monitoring data"

  statements = [
    # Metriche OCI Monitoring (CPU, RAM, rete, disco)
    "Allow dynamic-group grafana-monitor-dg to read metrics in compartment id ${var.compartment_ocid}",
    # Info istanze compute (nomi, shape, stato)
    "Allow dynamic-group grafana-monitor-dg to read instances in compartment id ${var.compartment_ocid}",
    # Compartment list (necessario per il plugin Grafana)
    "Allow dynamic-group grafana-monitor-dg to read compartments in tenancy",
    # VCN e subnet (metriche rete)
    "Allow dynamic-group grafana-monitor-dg to read vcns in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group grafana-monitor-dg to read subnets in compartment id ${var.compartment_ocid}",
    # OKE cluster metrics
    "Allow dynamic-group grafana-monitor-dg to read clusters in compartment id ${var.compartment_ocid}",
    # OCI Logging (per il plugin oci-logs-datasource)
    "Allow dynamic-group grafana-monitor-dg to read log-groups in compartment id ${var.compartment_ocid}",
    "Allow dynamic-group grafana-monitor-dg to read log-content in compartment id ${var.compartment_ocid}",
  ]
}

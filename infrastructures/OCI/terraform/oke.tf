# =============================================================================
# OKE Cluster (BASIC - free)
# =============================================================================

resource "oci_containerengine_cluster" "oke" {
  compartment_id     = var.compartment_ocid
  kubernetes_version = local.k8s_version
  name               = var.cluster_name
  vcn_id             = oci_core_vcn.oke_vcn.id
  type               = "BASIC_CLUSTER"

  cluster_pod_network_options {
    cni_type = "FLANNEL_OVERLAY"
  }

  endpoint_config {
    is_public_ip_enabled = true
    subnet_id            = oci_core_subnet.api_subnet.id
  }

  options {
    service_lb_subnet_ids = [oci_core_subnet.lb_subnet.id]

    kubernetes_network_config {
      pods_cidr     = "10.244.0.0/16"
      services_cidr = "10.96.0.0/16"
    }
  }
}

# =============================================================================
# Node Pool - Heavy (3 OCPU, 18 GB, 120 GB boot)
# =============================================================================

resource "oci_containerengine_node_pool" "heavy" {
  compartment_id     = var.compartment_ocid
  cluster_id         = oci_containerengine_cluster.oke.id
  kubernetes_version = local.k8s_version
  name               = "heavy-pool"
  node_shape         = "VM.Standard.A1.Flex"

  node_shape_config {
    ocpus         = var.heavy_pool_ocpus
    memory_in_gbs = var.heavy_pool_memory_gb
  }

  node_source_details {
    source_type             = "IMAGE"
    image_id                = local.oke_arm64_image_id
    boot_volume_size_in_gbs = var.heavy_pool_boot_volume_gb
  }

  node_config_details {
    size = var.heavy_pool_size

    placement_configs {
      availability_domain = data.oci_identity_availability_domain.ad.name
      subnet_id           = oci_core_subnet.node_subnet.id
    }
  }

  initial_node_labels {
    key   = "workload"
    value = "heavy"
  }

  ssh_public_key = var.ssh_public_key
}

# =============================================================================
# Node Pool - Light (1 OCPU, 6 GB, 40 GB boot)
# =============================================================================

resource "oci_containerengine_node_pool" "light" {
  compartment_id     = var.compartment_ocid
  cluster_id         = oci_containerengine_cluster.oke.id
  kubernetes_version = local.k8s_version
  name               = "light-pool"
  node_shape         = "VM.Standard.A1.Flex"

  node_shape_config {
    ocpus         = var.light_pool_ocpus
    memory_in_gbs = var.light_pool_memory_gb
  }

  node_source_details {
    source_type             = "IMAGE"
    image_id                = local.oke_arm64_image_id
    boot_volume_size_in_gbs = var.light_pool_boot_volume_gb
  }

  node_config_details {
    size = var.light_pool_size

    placement_configs {
      availability_domain = data.oci_identity_availability_domain.ad.name
      subnet_id           = oci_core_subnet.node_subnet.id
    }
  }

  initial_node_labels {
    key   = "workload"
    value = "light"
  }

  ssh_public_key = var.ssh_public_key
}

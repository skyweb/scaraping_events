# =============================================================================
# VCN
# =============================================================================

resource "oci_core_vcn" "oke_vcn" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "oke-vcn"
  dns_label      = "okvcn"
}

# =============================================================================
# Gateways
# =============================================================================

resource "oci_core_internet_gateway" "igw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.oke_vcn.id
  display_name   = "oke-igw"
  enabled        = true
}

resource "oci_core_service_gateway" "sgw" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.oke_vcn.id
  display_name   = "oke-sgw"

  services {
    service_id = local.oci_services_id
  }
}

# =============================================================================
# Route Tables
# =============================================================================

# Public route table (Internet Gateway)
resource "oci_core_route_table" "public_rt" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.oke_vcn.id
  display_name   = "oke-public-rt"

  route_rules {
    network_entity_id = oci_core_internet_gateway.igw.id
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
  }

  route_rules {
    network_entity_id = oci_core_service_gateway.sgw.id
    destination       = local.oci_services_cidr
    destination_type  = "SERVICE_CIDR_BLOCK"
  }
}

# =============================================================================
# Security Lists
# =============================================================================

# --- API Endpoint Subnet ---
resource "oci_core_security_list" "api_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.oke_vcn.id
  display_name   = "oke-api-sl"

  # Egress: all
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
    stateless   = false
  }

  # Ingress: K8s API 6443 da ovunque
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "Kubernetes API"
    tcp_options {
      min = 6443
      max = 6443
    }
  }

  # Ingress: OKE control plane to worker communication 12250
  ingress_security_rules {
    protocol    = "6"
    source      = "10.0.1.0/24"
    stateless   = false
    description = "OKE control plane from nodes"
    tcp_options {
      min = 12250
      max = 12250
    }
  }

  # Ingress: ICMP da node subnet
  ingress_security_rules {
    protocol    = "1"
    source      = "10.0.1.0/24"
    stateless   = false
    description = "ICMP from nodes"
  }
}

# --- Node Subnet ---
resource "oci_core_security_list" "node_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.oke_vcn.id
  display_name   = "oke-node-sl"

  # Egress: all
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
    stateless   = false
  }

  # Ingress: tutto il traffico intra-VCN (pod-to-pod, node-to-node)
  ingress_security_rules {
    protocol    = "all"
    source      = var.vcn_cidr
    stateless   = false
    description = "Intra-VCN traffic"
  }

  # Ingress: kubelet API da API subnet
  ingress_security_rules {
    protocol    = "6"
    source      = "10.0.0.0/28"
    stateless   = false
    description = "Kubelet API from control plane"
    tcp_options {
      min = 10250
      max = 10250
    }
  }

  # Ingress: NodePort da LB subnet
  ingress_security_rules {
    protocol    = "6"
    source      = "10.0.2.0/24"
    stateless   = false
    description = "NodePort from LB subnet"
    tcp_options {
      min = 30000
      max = 32767
    }
  }

  # Ingress: HTTP (Traefik hostPort per ACME HTTP-01 e redirect HTTPS)
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "HTTP for Traefik hostPort"
    tcp_options {
      min = 80
      max = 80
    }
  }

  # Ingress: HTTPS (Traefik hostPort per TLS termination)
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "HTTPS for Traefik hostPort"
    tcp_options {
      min = 443
      max = 443
    }
  }

  # Ingress: WireGuard VPN (NodePort UDP)
  ingress_security_rules {
    protocol    = "17"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "WireGuard VPN hostPort"
    udp_options {
      min = 51820
      max = 51820
    }
  }

  # Ingress: ICMP
  ingress_security_rules {
    protocol    = "1"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "ICMP"
  }
}

# --- Load Balancer Subnet ---
resource "oci_core_security_list" "lb_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.oke_vcn.id
  display_name   = "oke-lb-sl"

  # Egress: all
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
    stateless   = false
  }

  # Ingress: HTTP
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "HTTP"
    tcp_options {
      min = 80
      max = 80
    }
  }

  # Ingress: HTTPS
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "HTTPS"
    tcp_options {
      min = 443
      max = 443
    }
  }
}

# =============================================================================
# Subnets
# =============================================================================

# API Endpoint Subnet (public, /28)
resource "oci_core_subnet" "api_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.oke_vcn.id
  cidr_block        = "10.0.0.0/28"
  display_name      = "oke-api-subnet"
  dns_label         = "okeapi"
  route_table_id    = oci_core_route_table.public_rt.id
  security_list_ids = [oci_core_security_list.api_sl.id]
  dhcp_options_id   = oci_core_vcn.oke_vcn.default_dhcp_options_id
}

# Node Subnet (public, /24)
resource "oci_core_subnet" "node_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.oke_vcn.id
  cidr_block        = "10.0.1.0/24"
  display_name      = "oke-node-subnet"
  dns_label         = "okenode"
  route_table_id    = oci_core_route_table.public_rt.id
  security_list_ids = [oci_core_security_list.node_sl.id]
  dhcp_options_id   = oci_core_vcn.oke_vcn.default_dhcp_options_id
}

# Load Balancer Subnet (public, /24)
resource "oci_core_subnet" "lb_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.oke_vcn.id
  cidr_block        = "10.0.2.0/24"
  display_name      = "oke-lb-subnet"
  dns_label         = "okelb"
  route_table_id    = oci_core_route_table.public_rt.id
  security_list_ids = [oci_core_security_list.lb_sl.id]
  dhcp_options_id   = oci_core_vcn.oke_vcn.default_dhcp_options_id
}

# Micro VM Subnet (public, /28) - per le 2 micro VM standalone
resource "oci_core_subnet" "micro_subnet" {
  compartment_id    = var.compartment_ocid
  vcn_id            = oci_core_vcn.oke_vcn.id
  cidr_block        = "10.0.3.0/28"
  display_name      = "micro-vm-subnet"
  dns_label         = "microvms"
  route_table_id    = oci_core_route_table.public_rt.id
  security_list_ids = [oci_core_security_list.micro_sl.id]
  dhcp_options_id   = oci_core_vcn.oke_vcn.default_dhcp_options_id
}

# --- Micro VM Security List ---
resource "oci_core_security_list" "micro_sl" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.oke_vcn.id
  display_name   = "micro-vm-sl"

  # Egress: all
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
    stateless   = false
  }

  # Ingress: SSH
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "SSH"
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Ingress: HTTP (reverse proxy / Uptime Kuma)
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "HTTP"
    tcp_options {
      min = 80
      max = 80
    }
  }

  # Ingress: HTTPS
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "HTTPS"
    tcp_options {
      min = 443
      max = 443
    }
  }

  # Ingress: Prometheus / node-exporter (VCN only)
  ingress_security_rules {
    protocol    = "6"
    source      = var.vcn_cidr
    stateless   = false
    description = "Prometheus scrape from VCN"
    tcp_options {
      min = 9090
      max = 9100
    }
  }

  # Ingress: ICMP
  ingress_security_rules {
    protocol    = "1"
    source      = "0.0.0.0/0"
    stateless   = false
    description = "ICMP"
  }
}

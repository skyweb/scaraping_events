# =============================================================================
# Micro VMs (VM.Standard.E2.1.Micro - AMD x86_64, free tier)
# =============================================================================
# 2 istanze standalone fuori dal cluster OKE:
#   micro-1: Monitoring
#   micro-2: CI runner leggero
# =============================================================================

locals {
  micro_vm_names = ["micro-monitor", "micro-cirunner"]
}

resource "oci_core_instance" "micro_vm" {
  count = var.micro_vm_count

  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domain.ad.name
  display_name        = local.micro_vm_names[count.index]
  shape               = "VM.Standard.E2.1.Micro"

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.micro_amd64.images[0].id
    boot_volume_size_in_gbs = var.micro_vm_boot_volume_gb
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.micro_subnet.id
    display_name     = "${local.micro_vm_names[count.index]}-vnic"
    assign_public_ip = true
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
  }
}

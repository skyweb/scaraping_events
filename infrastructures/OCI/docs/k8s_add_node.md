# Aggiungere Nodi al Cluster OKE

Guida per scalare il cluster OKE `events-oke` aggiungendo nodi.

## Architettura Attuale

| Pool | Shape | OCPU | RAM | Boot | Label | Nodi |
|------|-------|------|-----|------|-------|------|
| heavy-pool | VM.Standard.A1.Flex (ARM64) | 3 | 18 GB | 120 GB | `workload=heavy` | 1 |
| light-pool | VM.Standard.A1.Flex (ARM64) | 1 | 6 GB | 40 GB | `workload=light` | 1 |

**Free Tier A1.Flex**: 4 OCPU + 24 GB RAM totali (attualmente **100% allocati**).

---

## 1. Scalare un Node Pool Esistente (Terraform)

Aumenta il numero di nodi in un pool esistente. Ogni nuovo nodo ha la stessa configurazione (shape, OCPU, RAM, label) del pool.

### Prerequisito: risorse disponibili

Verifica le risorse libere nel tenancy:

```bash
# Risorse A1.Flex usate
oci limits resource-availability get \
  --service-name compute \
  --limit-name standard-a1-core-count \
  --compartment-id $COMPARTMENT_OCID \
  --availability-domain $AD_NAME
```

### Modifica

In `terraform/terraform.tfvars`:

```hcl
# Esempio: aggiungere un secondo nodo heavy
heavy_pool_size = 2

# Oppure: aggiungere un secondo nodo light
light_pool_size = 2
```

### Applica

```bash
cd terraform

# Preview delle modifiche
terraform plan -var-file=terraform.tfvars

# Applica
terraform apply -var-file=terraform.tfvars
```

### Verifica

```bash
kubectl get nodes -o wide
kubectl get nodes --show-labels | grep workload
```

> **Nota Free Tier**: Con 4 OCPU / 24 GB gia' allocati, aggiungere nodi A1.Flex
> richiede prima di ridimensionare quelli esistenti (es. heavy da 3 a 2 OCPU)
> oppure passare a risorse a pagamento.

---

## 2. Creare un Nuovo Node Pool (Terraform)

Per workload con requisiti diversi (es. GPU, shape diversa, label specifiche).

### Aggiungi variabili

In `terraform/variables.tf`:

```hcl
# =============================================================================
# Node Pool - Custom
# =============================================================================

variable "custom_pool_ocpus" {
  description = "OCPU per il nodo custom"
  type        = number
  default     = 2
}

variable "custom_pool_memory_gb" {
  description = "GB di RAM per il nodo custom"
  type        = number
  default     = 12
}

variable "custom_pool_boot_volume_gb" {
  description = "GB boot volume per il nodo custom"
  type        = number
  default     = 50
}

variable "custom_pool_size" {
  description = "Numero di nodi nel pool custom"
  type        = number
  default     = 1
}
```

### Aggiungi risorsa

In `terraform/oke.tf`:

```hcl
# =============================================================================
# Node Pool - Custom (esempio: 2 OCPU, 12 GB)
# =============================================================================

resource "oci_containerengine_node_pool" "custom" {
  compartment_id     = var.compartment_ocid
  cluster_id         = oci_containerengine_cluster.oke.id
  kubernetes_version = local.k8s_version
  name               = "custom-pool"
  node_shape         = "VM.Standard.A1.Flex"

  node_shape_config {
    ocpus         = var.custom_pool_ocpus
    memory_in_gbs = var.custom_pool_memory_gb
  }

  node_source_details {
    source_type             = "IMAGE"
    image_id                = local.oke_arm64_image_id
    boot_volume_size_in_gbs = var.custom_pool_boot_volume_gb
  }

  node_config_details {
    size = var.custom_pool_size

    placement_configs {
      availability_domain = data.oci_identity_availability_domain.ad.name
      subnet_id           = oci_core_subnet.node_subnet.id
    }
  }

  initial_node_labels {
    key   = "workload"
    value = "custom"
  }

  ssh_public_key = var.ssh_public_key
}
```

### Applica e verifica

```bash
cd terraform
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars

# Verifica
kubectl get nodes --show-labels | grep custom
```

### Usare il nuovo pool

Nei manifest K8s, usa `nodeSelector` per schedulare pod sul pool:

```yaml
spec:
  nodeSelector:
    workload: custom
```

---

## 3. Aggiungere Worker Node Esterni (Self-Managed)

Aggiungere un nodo non gestito da OKE (es. VM on-premise, altra cloud) al cluster.

> **Importante**: OKE BASIC_CLUSTER con Flannel overlay **non supporta nativamente**
> l'aggiunta di nodi esterni. Le opzioni realistiche sono:

### Opzione A: Nodo nella stessa VCN OCI (consigliato)

Per VM OCI che non fanno parte di un Node Pool ma devono unirsi al cluster.

#### 1. Crea la VM

Crea un'istanza `VM.Standard.A1.Flex` (o E2.1.Micro) nella stessa VCN e subnet
dei nodi OKE (`oke-node-subnet`).

#### 2. Installa prerequisiti

```bash
ssh opc@<VM_IP>

# Oracle Linux 8 / Ubuntu - installa container runtime
sudo dnf install -y oracle-olcne-release-el8
sudo dnf install -y cri-o kubelet kubeadm kubectl
sudo systemctl enable --now crio kubelet
```

#### 3. Genera join token dal control plane

OKE gestisce il control plane, quindi il token va generato tramite API:

```bash
# Dal tuo laptop (con kubeconfig OKE configurato)
# Crea un bootstrap token
kubeadm token create --print-join-command 2>/dev/null
```

> **Attenzione**: Su OKE BASIC non hai accesso diretto al control plane.
> Il comando `kubeadm token create` **non funziona** perche' il control plane
> e' managed. Vedi le limitazioni sotto.

#### 4. Limitazioni OKE BASIC

| Funzionalita' | OKE BASIC | OKE Enhanced |
|---------------|-----------|--------------|
| Self-managed nodes | No | Si (Virtual Nodes) |
| Accesso control plane SSH | No | No |
| `kubeadm token create` | No | No |
| API node registration | No | Si |

**Conclusione**: Su OKE BASIC_CLUSTER, **non e' possibile aggiungere worker node
esterni**. Il control plane e' completamente gestito da Oracle e non espone
l'endpoint di bootstrap necessario per il join.

### Opzione B: Cluster ibrido con K3s/K0s (alternativa)

Se hai bisogno di nodi esterni (on-premise, altra cloud), l'approccio consigliato
e' un cluster K3s/K0s separato con federazione:

```
OKE Cluster (OCI)              K3s Cluster (esterno)
├── events namespace            ├── workload namespace
├── monitoring namespace        └── (pod schedulati qui)
└── Traefik ingress
         \                          /
          └── Submariner / Skupper ─┘
              (multi-cluster networking)
```

Strumenti per multi-cluster:
- **Submariner**: tunnel L3 tra cluster
- **Skupper**: service mesh multi-cluster (layer 7)
- **Liqo**: virtual kubelet per scheduling cross-cluster

> Questa e' una configurazione avanzata, consigliata solo se le risorse OCI
> Free Tier non sono sufficienti.

---

## 4. Ridimensionare i Nodi Esistenti

Se il Free Tier e' esaurito, puoi redistribuire OCPU/RAM tra i pool.

### Esempio: da 3+1 a 2+2 OCPU

In `terraform/terraform.tfvars`:

```hcl
# Prima: heavy=3 OCPU, light=1 OCPU (tot: 4)
# Dopo:  heavy=2 OCPU, light=2 OCPU (tot: 4)
heavy_pool_ocpus     = 2
heavy_pool_memory_gb = 12
light_pool_ocpus     = 2
light_pool_memory_gb = 12
```

```bash
cd terraform
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

> **Attenzione**: Il ridimensionamento ricrea i nodi. I pod verranno rischedulati
> automaticamente, ma ci sara' un breve downtime. Esegui un backup Velero prima:
> ```bash
> velero backup create pre-resize --include-namespaces events,monitoring
> ```

---

## 5. Best Practice

### Label e Taint

Usa label per separare i workload:

```bash
# Verifica label attuali
kubectl get nodes --show-labels

# Aggiungi taint per riservare un pool (opzionale)
kubectl taint nodes -l workload=heavy dedicated=heavy:NoSchedule
```

Nei deployment, aggiungi toleration:

```yaml
spec:
  nodeSelector:
    workload: heavy
  tolerations:
    - key: dedicated
      operator: Equal
      value: heavy
      effect: NoSchedule
```

### Monitoraggio risorse

```bash
# Risorse allocate vs disponibili per nodo
kubectl describe nodes | grep -A 5 "Allocated resources"

# Top nodi (richiede metrics-server)
kubectl top nodes

# Pod per nodo
kubectl get pods -A -o wide --sort-by=.spec.nodeName
```

### Drain prima di rimuovere

```bash
# Evacua i pod prima di rimuovere un nodo
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Poi riduci il pool via Terraform
```

---

## Riepilogo Limiti Free Tier OCI

| Risorsa | Limite Free Tier | Uso Attuale |
|---------|------------------|-------------|
| A1.Flex OCPU | 4 | 4 (3 heavy + 1 light) |
| A1.Flex RAM | 24 GB | 24 GB (18 + 6) |
| E2.1.Micro | 2 istanze | 2 (micro VM) |
| Boot Volume | 200 GB totale | 260 GB* |
| Object Storage | 20 GB Standard | velero-backups |

\* I boot volume oltre 50 GB per i nodi A1.Flex sono a pagamento (Block Volume).

Per aggiungere capacita' senza costi aggiuntivi:
1. **Ridimensiona** i pool esistenti (sezione 4)
2. **Usa le micro VM** per servizi leggeri (Grafana e' gia' li')
3. **Ottimizza i resource limits** dei pod (riduci CPU/memory limit)

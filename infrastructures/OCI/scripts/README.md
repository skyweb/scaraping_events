# Scripts OCI — Guida al Deploy

Raccolta di script per creare e configurare l'infrastruttura OCI (cluster OKE + micro VM + servizi K8s).

## Prerequisiti

- [OCI CLI](https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm) configurato (`~/.oci/config`)
- [Terraform](https://www.terraform.io/) >= 1.5
- [Ansible](https://docs.ansible.com/) >= 2.15 + `ansible-vault`
- `kubectl`, `helm`, `jq`
- File `terraform/terraform.tfvars` compilato (copia da `terraform.tfvars.example`)

## Script disponibili

### Infrastruttura (Terraform)

| Script | Descrizione |
|---|---|
| `deploy.sh` | Deploy completo: `terraform init` + `plan` + `apply`, configura kubeconfig, attende che i 2 nodi siano Ready, genera il summary |
| `destroy.sh` | Distrugge tutta l'infrastruttura OCI (`terraform destroy`) con conferma interattiva |
| `get-kubeconfig.sh` | Recupera il kubeconfig dal cluster OKE e lo salva in `~/.kube/config` |

### Generazione configurazione

| Script | Descrizione |
|---|---|
| `generate-vars.sh` | Legge gli output Terraform e genera `ansible/vars/oke.yml` (config) + `ansible/vars/oke-vault.yml` (secret da criptare) |
| `generate-inventory.sh` | Legge gli output Terraform e genera `ansible/inventory/hosts.yml` con IP delle micro VM |
| `generate-summary.sh` | Genera `docs/deploy-summary.md` con tutti gli endpoint, IP, comandi SSH e URL servizi |
| `generate-ssh-key.sh` | Genera la coppia di chiavi SSH (`oci-key` / `oci-key.pub`) per accedere alle micro VM |

### Configurazione cluster (Ansible)

| Script | Descrizione |
|---|---|
| `post-setup.sh` | Esegue `post-cluster-setup.yml` (infrastruttura base: Traefik, cert-manager, metrics-server, K8s Dashboard) |
| `setup-all.sh` | Esegue **tutti** i playbook Ansible in sequenza (infrastruttura, data services, CI/CD, observability, security, backup, app, domain, reverse proxy) |

### Utility OCI

| Script | Descrizione |
|---|---|
| `get_oci_info.sh` | Mostra tenancy OCID, user OCID, compartment, fingerprint e region dalla configurazione OCI locale |
| `get_ocir_config.sh` | Recupera automaticamente la configurazione OCIR (registry, namespace, username) e genera un auth token |
| `configure-ocir.sh` | Configura OCIR con Portainer: crea `ansible/vars/ocir.yml` e lancia il playbook di configurazione |
| `list-instances.sh` | Elenca tutte le istanze compute OCI con stato, shape, OCPU, RAM e IP |

## Sequenza di deploy

### Fase 1 — Infrastruttura (Terraform)

Crea: VCN, subnet, security list, cluster OKE (2 node pool), 2 micro VM, bucket Object Storage, OCIR, IAM.

```bash
# 1. Genera chiave SSH per le micro VM (se non esiste)
./scripts/generate-ssh-key.sh

# 2. Configura terraform.tfvars
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# Editare con i propri OCID (tenancy, user, compartment, fingerprint, key path)

# 3. Deploy infrastruttura (~20 minuti)
./scripts/deploy.sh
```

Al termine si avranno:
- Cluster OKE con 2 nodi (heavy 3 OCPU/18GB + light 1 OCPU/6GB)
- 2 micro VM (micro-monitor + micro-gw)
- Bucket `velero-backups`
- 2 repository OCIR (`events/backoffice`, `events/scraping`)
- Kubeconfig configurato

### Fase 2 — Generazione configurazione Ansible

Genera i file di configurazione per Ansible a partire dagli output Terraform.

```bash
# 4. Genera variabili Ansible (oke.yml + oke-vault.yml)
./scripts/generate-vars.sh

# 5. Editare oke-vault.yml: cambiare password di default
ansible-vault edit ansible/vars/oke-vault.yml

# 6. Genera inventory Ansible (hosts.yml con IP micro VM)
./scripts/generate-inventory.sh
```

### Fase 3 — Configurazione cluster (Ansible)

Installa tutti i servizi sul cluster K8s e sulle micro VM.

**Opzione A — Tutto in una volta:**

```bash
# 7. Setup completo (tutti i playbook in sequenza)
./scripts/setup-all.sh
```

**Opzione B — Step by step:**

```bash
# 7a. Infrastruttura base (Traefik, cert-manager, metrics-server, K8s Dashboard)
./scripts/post-setup.sh --ask-vault-pass

# 7b. Data Services (PostgreSQL, Redis)
ansible-playbook ansible/playbooks/data-setup.yml --ask-vault-pass

# 7c. CI/CD (ArgoCD, Tekton, Kaniko)
ansible-playbook ansible/playbooks/ci-setup.yml --ask-vault-pass

# 7d. Observability K8s (Prometheus, Loki, Promtail, OTel Collector, Jaeger)
ansible-playbook ansible/playbooks/observability-cluster-setup.yml --ask-vault-pass

# 7e. Security (Kyverno + 6 ClusterPolicy)
ansible-playbook ansible/playbooks/security-setup.yml --ask-vault-pass

# 7f. Backup (Velero + schedule giornaliero/settimanale)
ansible-playbook ansible/playbooks/backup-setup.yml --ask-vault-pass

# 7g. Grafana su micro-monitor VM
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/observability-vm-setup.yml --ask-vault-pass

# 7h. Application (Secret + ArgoCD Application per Backoffice e Airflow)
ansible-playbook ansible/playbooks/app-setup.yml --ask-vault-pass

# 7i. HTTPS routing (IngressRoute + OAuth2 Proxy)
ansible-playbook ansible/playbooks/domain-setup.yml --ask-vault-pass

# 7j. TCP Forwarding (micro-gw, firewalld DNAT → Traefik K8s)
ansible-playbook -i ansible/inventory/hosts.yml ansible/playbooks/reverse-proxy-setup.yml --ask-vault-pass
```

### Riepilogo sequenza

```
generate-ssh-key.sh          Chiave SSH
        │
    deploy.sh                Terraform (VCN, OKE, VM, OCIR, bucket)
        │
   ┌────┴────┐
   │         │
generate-  generate-
vars.sh    inventory.sh      Configurazione Ansible
   │         │
   └────┬────┘
        │
   setup-all.sh              Ansible (tutti i playbook)
        │
        ├── post-cluster-setup     Traefik, cert-manager, metrics-server, Dashboard
        ├── data-setup             PostgreSQL, Redis
        ├── ci-setup               ArgoCD, Tekton
        ├── observability-cluster  Prometheus, Loki, Promtail, OTel, Jaeger
        ├── security-setup         Kyverno (6 policy)
        ├── backup-setup           Velero (backup giornaliero + settimanale)
        ├── observability-vm       Grafana (micro-monitor VM)
        ├── app-setup              Secret + ArgoCD App (Backoffice, Airflow)
        ├── domain-setup           IngressRoute + Auth (OAuth2 Proxy)
        └── reverse-proxy-setup    TCP forwarding (micro-gw, firewalld DNAT)
```

## Distruzione

```bash
./scripts/destroy.sh
```

Distrugge tutte le risorse OCI create da Terraform (cluster, VM, VCN, bucket, OCIR).
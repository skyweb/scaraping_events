# Scraping Service — K8s Manifests

Pod effimeri per spider Scrapy, orchestrati da Airflow via `KubernetesPodOperator`.

## Architettura

- **Nessun deployment persistente** — i pod spider vengono creati e distrutti dal DAG Airflow
- **Namespace dedicato** `scraping` — isolamento RBAC dal resto del cluster
- **Airflow Scheduler** (ns `airflow`) ha permessi per creare pod in ns `scraping`

## Build e Push immagine OCIR

```bash
# Build multi-arch (ARM64 per OKE A1.Flex)
docker buildx build \
  --platform linux/arm64 \
  -t eu-milan-1.ocir.io/axbuakdjv1li/events/scraping:latest \
  -f microservices/scraping-service/Dockerfile \
  microservices/scraping-service/ \
  --push

# Oppure via Tekton Pipeline (CI)
# Il pipeline kaniko-build gestisce build + push automaticamente
```

## Deploy

```bash
# Prerequisito: namespace scraping + imagePullSecret creati da ansible
ansible-playbook ansible/playbooks/scraping-setup.yml --ask-vault-pass

# Oppure manualmente:
kubectl create namespace scraping
kubectl apply -k k8s/scraping-service/
```

## Verifica RBAC

```bash
# L'Airflow Scheduler deve poter creare pod nel namespace scraping
kubectl auth can-i create pods \
  --as=system:serviceaccount:airflow:airflow-scheduler \
  -n scraping
# Atteso: yes
```

# Monitoring Stack - K8s Manifests

Observability stack per il cluster OKE. Comprende Helm values files per chart complessi
e manifest K8s nativi per deployment semplici e route APISIX.

## Prerequisiti

```bash
# Namespace
kubectl create namespace monitoring

# Secret per Redis e Celery exporter
kubectl create secret generic monitoring-secret --namespace monitoring \
  --from-literal=REDIS_PASSWORD=<PASSWORD> \
  --from-literal=CELERY_BROKER_URL=<BROKER_URL>

# Secret per Grafana admin password
kubectl create secret generic grafana-secret --namespace monitoring \
  --from-literal=GF_SECURITY_ADMIN_PASSWORD=<GRAFANA_ADMIN_PASSWORD>

# Helm repos
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
```

## Installazione Helm Charts

```bash
helm upgrade --install prometheus prometheus-community/prometheus \
  -n monitoring -f prometheus-values.yml

helm upgrade --install loki grafana/loki \
  -n monitoring -f loki-values.yml

helm upgrade --install alloy grafana/alloy \
  -n monitoring -f alloy-values.yml

helm upgrade --install tempo grafana/tempo \
  -n monitoring -f tempo-values.yml

helm upgrade --install grafana grafana/grafana \
  -n monitoring -f grafana-values.yml

helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  -n monitoring -f otel-collector-values.yml
```

## Manifest Nativi (Kustomize)

Applica deployment, service e route APISIX:

```bash
kubectl apply -k .
```

Risorse incluse:
- **monitoring-apisix-routes**: Route APISIX per Prometheus, Grafana (SSO via Keycloak)
- **dashboard-apisix-route**: Route APISIX per K8s Dashboard

## Verifica

```bash
# Pod status
kubectl get pods -n monitoring

# Services
kubectl get svc -n monitoring

# Helm releases
helm list -n monitoring
```

## Componenti

| Componente | Tipo | Accesso |
|---|---|---|
| Prometheus | Helm chart | prometheus.${DOMAIN} |
| Alertmanager | Helm chart (sub-chart) | interno |
| Loki | Helm chart (SingleBinary) | interno (log backend) |
| Alloy | Helm chart (DaemonSet) | interno (log collector, metriche su :12345) |
| OTEL Collector | Helm chart (DaemonSet) | interno (OTLP receiver) |
| Tempo | Helm chart (SingleBinary) | interno (trace backend) |
| Grafana | Helm chart | grafana.${DOMAIN} |
| PostgreSQL Exporter | Helm chart | interno (ClusterIP) |
| Redis Exporter | K8s Deployment | interno (ClusterIP :9121) |
| Celery Exporter | K8s Deployment | interno (ClusterIP :9808) |

# Monitoring Stack - K8s Manifests

Observability stack per il cluster OKE. Comprende Helm values files per chart complessi
e manifest K8s nativi per deployment semplici e IngressRoute.

## Prerequisiti

```bash
# Namespace
kubectl create namespace monitoring

# Secret per Redis e Celery exporter
kubectl create secret generic monitoring-secret --namespace monitoring \
  --from-literal=REDIS_PASSWORD=<PASSWORD> \
  --from-literal=CELERY_BROKER_URL=<BROKER_URL>

# Helm repos
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm repo update
```

## Installazione Helm Charts

```bash
helm upgrade --install prometheus prometheus-community/prometheus \
  -n monitoring -f prometheus-values.yml

helm upgrade --install loki grafana/loki \
  -n monitoring -f loki-values.yml

helm upgrade --install promtail grafana/promtail \
  -n monitoring -f promtail-values.yml

helm upgrade --install otel-collector open-telemetry/opentelemetry-collector \
  -n monitoring -f otel-collector-values.yml

helm upgrade --install jaeger jaegertracing/jaeger \
  -n monitoring -f jaeger-values.yml
```

## Manifest Nativi (Kustomize)

Applica deployment, service e IngressRoute:

```bash
kubectl apply -k .
```

Risorse incluse:
- **redis-exporter**: Deployment + Service (porta 9121), metriche Redis per Prometheus
- **celery-exporter**: Deployment + Service (porta 9808), metriche Celery per Prometheus
- **IngressRoute**: prometheus, alertmanager, loki, jaeger, K8s Dashboard, Traefik Dashboard

## Verifica

```bash
# Pod status
kubectl get pods -n monitoring

# Services
kubectl get svc -n monitoring

# IngressRoute
kubectl get ingressroute -n monitoring
kubectl get ingressroute -n traefik

# Helm releases
helm list -n monitoring
```

## Componenti

| Componente | Tipo | Accesso |
|---|---|---|
| Prometheus | Helm chart | prometheus.oci.santocaruso.eu |
| Alertmanager | Helm chart (sub-chart) | alertmanager.oci.santocaruso.eu |
| Loki | Helm chart (SingleBinary) | loki.oci.santocaruso.eu |
| Promtail | Helm chart (DaemonSet) | interno (log shipper) |
| OTEL Collector | Helm chart (DaemonSet) | interno (OTLP receiver) |
| Jaeger | Helm chart (All-in-One) | jaeger.oci.santocaruso.eu |
| Redis Exporter | K8s Deployment | interno (ClusterIP :9121) |
| Celery Exporter | K8s Deployment | interno (ClusterIP :9808) |
| K8s Dashboard | IngressRoute only | dashboard.oci.santocaruso.eu |
| Traefik Dashboard | IngressRoute only | traefik.oci.santocaruso.eu |

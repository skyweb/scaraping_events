# Backoffice Events (Django + Celery)

Deployment Django backoffice con Celery worker e beat, namespace `events`, nodo heavy.

## File

| File | Contenuto |
|---|---|
| `backoffice-configmap.yml` | ConfigMap con configurazione Django: debug off, allowed hosts, PostgreSQL connection, CORS/CSRF origins, OpenTelemetry disabilitato |
| `backoffice-deployment.yml` | Deployment RollingUpdate, immagine OCIR `events/backoffice:latest`, porta 8000, nodo heavy, 100m/256Mi req, 500m/512Mi limits, readiness/liveness su `/api/version/` |
| `backoffice-service.yml` | Service ClusterIP su porta 8000 |
| `celery-worker-deployment.yml` | Deployment Recreate, `celery worker`, nodo heavy, 200m/512Mi req, 1000m/1Gi limits, liveness via `celery inspect ping` |
| `celery-beat-deployment.yml` | Deployment Recreate, `celery beat` con DatabaseScheduler, nodo heavy, 50m/128Mi req, 200m/256Mi limits |
| `backoffice-ingressroute.yml` | IngressRoute Traefik Host-based `events.oci.santocaruso.eu` verso `backoffice:8000`, no auth middleware (auth nativa Django) |

## Prerequisiti

- Namespace `events` esistente:
  ```bash
  kubectl create namespace events
  ```
- PostgreSQL e Redis deployati (`k8s/postgres/`, `k8s/redis/`)
- Secret `backoffice-secret` con credenziali Django, DB, Redis, Celery:
  ```bash
  kubectl create secret generic backoffice-secret \
    --namespace events \
    --from-literal=SECRET_KEY=<DJANGO_SECRET_KEY> \
    --from-literal=POSTGRES_PASSWORD=<PASSWORD> \
    --from-literal=CELERY_BROKER_URL=redis://:<REDIS_PASSWORD>@redis.events.svc:6379/0 \
    --from-literal=CACHE_REDIS_URL=redis://:<REDIS_PASSWORD>@redis.events.svc:6379/1 \
    --from-literal=DJANGO_SUPERUSER_USERNAME=admin \
    --from-literal=DJANGO_SUPERUSER_EMAIL=admin@events.local \
    --from-literal=DJANGO_SUPERUSER_PASSWORD=<PASSWORD>
  ```
- Immagine Docker pushata su OCIR
- Traefik Ingress Controller installato
- DNS A record: `events.oci.santocaruso.eu` verso IP pubblico

## Installazione

```bash
# Applica i manifest
kubectl apply -k infrastructures/OCI/k8s/events/

# Verifica
kubectl rollout status deployment backoffice --namespace events --timeout=180s
kubectl rollout status deployment celery-worker --namespace events --timeout=120s
kubectl rollout status deployment celery-beat --namespace events --timeout=120s
kubectl get pods -n events -l app=backoffice
kubectl get ingressroute -n events
```

## Accesso

Dopo l'applicazione della IngressRoute, il servizio e' raggiungibile su:

```
https://events.oci.santocaruso.eu
```

## Connessione interna

```
backoffice.events.svc:8000
```

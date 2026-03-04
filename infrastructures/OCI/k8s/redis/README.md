# Redis 7 Alpine

Deployment Redis con persistenza AOF, namespace `database`, nodo light.

## File

| File | Contenuto |
|---|---|
| `redis-pvc.yml` | PVC 2Gi ReadWriteOnce per dati Redis |
| `redis-deployment.yml` | Deployment Recreate, `redis:7-alpine`, nodo light, `--requirepass` + `--appendonly yes` + `--appendfsync everysec`, 50m/64Mi req, 200m/128Mi limits, readiness/liveness via `redis-cli ping` |
| `redis-service.yml` | Service ClusterIP su porta 6379 |

## Prerequisiti

- Namespace `events` esistente:
  ```bash
  kubectl create namespace database
  ```
- Secret `redis-secret` con chiave `REDIS_PASSWORD`

## Installazione

```bash
# Crea il Secret
kubectl create secret generic redis-secret \
  --namespace database \
  --from-literal=REDIS_PASSWORD=<PASSWORD>

# Applica i manifest
kubectl apply -k infrastructures/OCI/k8s/redis/

# Verifica
kubectl rollout status deployment redis --namespace database --timeout=120s
kubectl get pods -n database -l app=redis
```

## Accesso

Redis e' un servizio interno al cluster, non esposto via IngressRoute.

## Connessione interna

```
redis.database.svc:6379
```

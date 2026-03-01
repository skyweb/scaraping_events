# Apache Airflow 2.9.2

Webserver + Scheduler con LocalExecutor e git-sync per DAGs, namespace `airflow`, nodo heavy.

## File

| File | Contenuto |
|---|---|
| `airflow-configmap.yml` | ConfigMap con configurazione Airflow: LocalExecutor, DAG folder via git-sync, base URL, parallelism 4, max 2 task/DAG, gunicorn 300s timeout |
| `airflow-pvc.yml` | PVC 5Gi ReadWriteOnce per logs Airflow |
| `airflow-init-job.yml` | Job ArgoCD PreSync: `db migrate` + creazione utente admin, `airflow:2.9.2`, nodo heavy, 100m/256Mi req, 500m/512Mi limits |
| `airflow-webserver-deployment.yml` | Deployment RollingUpdate, `airflow:2.9.2`, porta 8080, nodo heavy, 200m/512Mi req, 1CPU/1Gi limits, git-sync sidecar, startup/readiness/liveness su `/health` |
| `airflow-scheduler-deployment.yml` | Deployment Recreate, `airflow:2.9.2`, nodo heavy, 100m/256Mi req, 500m/512Mi limits, git-sync sidecar, liveness via scheduler job check |
| `airflow-service.yml` | Service ClusterIP su porta 8080 |
| `airflow-ingressroute.yml` | IngressRoute Traefik Host-based `airflow.oci.santocaruso.eu` verso `airflow-webserver:8080`, con middleware `google-auth` (OAuth2 Proxy) |

## Prerequisiti

- Namespace `airflow` esistente:
  ```bash
  kubectl create namespace airflow
  ```
- PostgreSQL deployato (`k8s/postgres/`) con database `airflow`
- Secret `airflow-secret` con credenziali DB e admin:
  ```bash
  kubectl create secret generic airflow-secret \
    --namespace airflow \
    --from-literal=AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://<USER>:<PASSWORD>@postgres.events.svc:5432/airflow \
    --from-literal=AIRFLOW__WEBSERVER__SECRET_KEY=<SECRET_KEY> \
    --from-literal=AIRFLOW_ADMIN_PASSWORD=<PASSWORD>
  ```
- Repository Git accessibile per git-sync DAGs
- Traefik Ingress Controller installato con middleware `google-auth` nel namespace `traefik`
- DNS A record: `airflow.oci.santocaruso.eu` verso IP pubblico

## Installazione

```bash
# Applica i manifest
kubectl apply -k infrastructures/OCI/k8s/airflow/

# Verifica
kubectl rollout status deployment airflow-webserver --namespace airflow --timeout=180s
kubectl rollout status deployment airflow-scheduler --namespace airflow --timeout=180s
kubectl get pods -n airflow
kubectl get ingressroute -n airflow
```

## Accesso

Dopo l'applicazione della IngressRoute, il servizio e' raggiungibile su:

```
https://airflow.oci.santocaruso.eu
```

L'accesso richiede autenticazione Google SSO (OAuth2 Proxy).

## Connessione interna

```
airflow-webserver.airflow.svc:8080
```

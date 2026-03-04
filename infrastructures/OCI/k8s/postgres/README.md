# PostgreSQL 16 + PostGIS 3.4

StatefulSet PostgreSQL con estensioni PostGIS, namespace `database`, nodo heavy.

## File

| File | Contenuto |
|---|---|
| `postgres-configmap.yml` | ConfigMap `postgres-init-scripts` con script SQL: postgis, postgis_topology, pg_trgm |
| `postgres-pvc.yml` | PVC 20Gi ReadWriteOnce per dati PostgreSQL |
| `postgres-statefulset.yml` | StatefulSet `postgis:16-3.4`, nodo heavy, 100m/256Mi req, 800m/1Gi limits, readiness/liveness via `pg_isready` |
| `postgres-service.yml` | Service ClusterIP su porta 5432 |

## Prerequisiti

- Namespace `events` esistente:
  ```bash
  kubectl create namespace database
  ```
- Secret `postgres-secret` con chiavi `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`

## Installazione

```bash
# Crea il Secret
kubectl create secret generic postgres-secret \
  --namespace database \
  --from-literal=POSTGRES_USER=events \
  --from-literal=POSTGRES_PASSWORD=<PASSWORD> \
  --from-literal=POSTGRES_DB=events

# Applica i manifest
kubectl apply -k infrastructures/OCI/k8s/postgres/

# Verifica
kubectl rollout status statefulset postgres --namespace database --timeout=180s
kubectl get pods -n database -l app=postgres
```

## Connessione interna

```
postgres.database.svc:5432
```

## Accesso remoto

PostgreSQL e' un servizio interno al cluster (ClusterIP), non esposto via IngressRoute.
Di seguito le opzioni per raggiungerlo da remoto.

### Opzione 1: kubectl port-forward (consigliata)

Nessuna modifica al cluster. Richiede `kubectl` configurato localmente.

```bash
kubectl port-forward svc/postgres 5432:5432 -n database
```

Poi connettiti a `localhost:5432`:

```bash
psql -h localhost -p 5432 -U events -d events
```

### Opzione 2: SSH tunnel verso un nodo K8s

Tunnel SSH verso un nodo del cluster che puo' raggiungere il ClusterIP di postgres.

```bash
# Trova il ClusterIP
kubectl get svc postgres -n database -o jsonpath='{.spec.clusterIP}'

# Tunnel SSH (sostituisci <CLUSTER_IP> con il valore ottenuto)
ssh -L 5432:<CLUSTER_IP>:5432 user@<K8S_NODE_IP>
```

Poi connettiti a `localhost:5432` dal tuo PC.

### Opzione 3: SSH jump via micro-gw

Se non hai accesso SSH diretto ai nodi K8s ma hai la micro-gw:

```bash
ssh -J user@<MICRO_GW_PUBLIC_IP> \
    -L 5432:postgres.database.svc.cluster.local:5432 \
    user@<K8S_NODE_PRIVATE_IP>
```

### Opzione 4: NodePort Service (accesso diretto via IP)

Aggiungere un secondo Service di tipo NodePort per esporre PostgreSQL su una porta del nodo.

```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  name: postgres-nodeport
  namespace: database
spec:
  type: NodePort
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
      nodePort: 31432
EOF
```

Poi connettiti direttamente:

```bash
psql -h <K8S_NODE_IP> -p 31432 -U events -d events
```

> **Attenzione:** questa opzione espone il DB sulla rete. Assicurarsi che la security list OCI
> limiti l'accesso alla porta 31432 ai soli IP autorizzati.

### Riepilogo opzioni

| Opzione | Modifiche cluster | Sicurezza | Praticita' |
|---|---|---|---|
| 1. kubectl port-forward | Nessuna | Alta | Buona (richiede kubectl) |
| 2. SSH tunnel al nodo | Nessuna | Alta | Buona (richiede SSH) |
| 3. SSH jump via micro-gw | Nessuna | Alta | Media (doppio hop) |
| 4. NodePort | Aggiunta Service | Bassa (porta esposta) | Alta (accesso diretto) |

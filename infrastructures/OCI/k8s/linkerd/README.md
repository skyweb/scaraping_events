# Linkerd — Service Mesh con mTLS

Service mesh leggero che aggiunge mTLS automatico tra i pod del cluster.
L'installazione e' opt-in: Linkerd non interferisce con i namespace dove non e' abilitato.

## File

| File | Contenuto |
|---|---|
| `linkerd-values.yml` | Helm values per il control plane: nodeSelector light, risorse limitate, identity via cert-manager |
| `linkerd-viz-values.yml` | Helm values per la dashboard viz: riusa Prometheus esistente, no Prometheus interno |
| `linkerd-viz-ingressroute.yml` | IngressRoute Traefik per dashboard `linkerd.oci.santocaruso.eu` + Middleware headers + google-auth |
| `kustomization.yml` | Kustomize per IngressRoute e Middleware |

## Prerequisiti

- cert-manager installato (`post-cluster-setup.yml`)
- Traefik installato (`traefik-setup.yml`)
- OAuth2 Proxy installato (`domain-setup.yml`)
- DNS A record: `linkerd.oci.santocaruso.eu`

## Installazione

```bash
ansible-playbook ansible/playbooks/linkerd-setup.yml --ask-vault-pass
```

Il playbook:
1. Crea i certificati trust anchor e identity issuer via cert-manager
2. Installa Linkerd CRDs, control plane e viz via Helm
3. Applica IngressRoute per la dashboard

## Come funziona mTLS

Linkerd inietta un sidecar proxy in ogni pod dei namespace abilitati.
Il proxy gestisce automaticamente la crittografia mTLS tra i servizi, senza modifiche al codice.

```
Pod A                              Pod B
[app] -> [linkerd-proxy] --mTLS-> [linkerd-proxy] -> [app]
```

I certificati vengono ruotati automaticamente ogni 48h da cert-manager.

## Abilitare mTLS su un namespace

```bash
# 1. Abilita l'injection sul namespace
kubectl annotate namespace apps linkerd.io/inject=enabled

# 2. Riavvia i deployment per iniettare il sidecar
kubectl rollout restart deployment -n apps
```

## Disabilitare mTLS su un namespace

```bash
# 1. Rimuovi l'annotazione
kubectl annotate namespace apps linkerd.io/inject-

# 2. Riavvia i deployment per rimuovere il sidecar
kubectl rollout restart deployment -n apps
```

## Escludere un singolo pod

Se un namespace ha mTLS abilitato ma vuoi escludere un pod specifico:

```yaml
metadata:
  annotations:
    linkerd.io/inject: disabled
```

## Esempio: abilitare mTLS progressivamente

Ordine consigliato per abilitare mTLS nel cluster:

```bash
# 1. Inizia dal namespace database (postgres, redis, celery)
kubectl annotate namespace database linkerd.io/inject=enabled
kubectl rollout restart deployment -n database
kubectl rollout restart statefulset -n database

# 2. Poi apps (backoffice Django)
kubectl annotate namespace apps linkerd.io/inject=enabled
kubectl rollout restart deployment -n apps

# 3. Poi airflow
kubectl annotate namespace airflow linkerd.io/inject=enabled
kubectl rollout restart deployment -n airflow

# 4. Poi devs (backstage, sonarqube)
kubectl annotate namespace devs linkerd.io/inject=enabled
kubectl rollout restart deployment -n devs
kubectl rollout restart statefulset -n devs
```

## Verifica mTLS

```bash
# Verifica che il sidecar sia stato iniettato (2/2 = sidecar presente)
kubectl get pods -n apps -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .spec.containers[*]}{.name}{" "}{end}{"\n"}{end}'

# Verifica connessioni mTLS attive
linkerd viz edges deployment -n apps

# Verifica stato generale
linkerd check

# Dashboard (se non hai IngressRoute configurato)
linkerd viz dashboard
```

## Metriche e monitoring

Linkerd Viz riusa il Prometheus esistente in `monitoring` (non installa un Prometheus dedicato).
Le metriche sono visibili nella dashboard a `https://linkerd.oci.santocaruso.eu`.

Metriche disponibili:
- Success rate per servizio
- Request rate (RPS)
- Latenza (p50, p95, p99)
- Connessioni mTLS attive

## Comandi utili

```bash
# Stato del mesh
linkerd check

# Top richieste in tempo reale
linkerd viz top deployment -n apps

# Statistiche per namespace
linkerd viz stat deploy -n apps

# Tap: intercetta richieste live (debug)
linkerd viz tap deployment/backoffice -n apps

# Verifica che mTLS sia attivo tra due servizi
linkerd viz edges deployment -n database
```

## Rimozione completa

Per rimuovere Linkerd senza impatto sui servizi:

```bash
# 1. Rimuovi annotazioni da tutti i namespace
kubectl annotate namespace apps linkerd.io/inject-
kubectl annotate namespace database linkerd.io/inject-
# ... ripeti per ogni namespace abilitato

# 2. Riavvia i deployment per rimuovere i sidecar
kubectl rollout restart deployment -n apps
kubectl rollout restart deployment -n database

# 3. Disinstalla Helm
helm uninstall linkerd-viz -n linkerd-viz
helm uninstall linkerd-control-plane -n linkerd
helm uninstall linkerd-crds -n linkerd

# 4. Rimuovi namespace
kubectl delete namespace linkerd-viz
kubectl delete namespace linkerd
```

## Architettura

```
Namespace: linkerd
  - linkerd-destination    (service discovery + policy)
  - linkerd-identity       (mTLS certificate authority)
  - linkerd-proxy-injector (inietta sidecar nei pod)

Namespace: linkerd-viz
  - web                    (dashboard UI)
  - metrics-api            (query metriche da Prometheus)
  - tap                    (intercetta richieste live)
  - tap-injector           (abilita tap sui pod)

Certificati (gestiti da cert-manager):
  - linkerd-trust-anchor   (CA root, durata 10 anni)
  - linkerd-identity-issuer (issuer intermedio, auto-rotate 48h)
```

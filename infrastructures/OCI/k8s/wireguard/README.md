# WireGuard VPN (wg-easy)

Server VPN WireGuard con Web UI per gestione peer, namespace `wireguard`, nodo light.

## File

| File | Contenuto |
|---|---|
| `wireguard-pvc.yml` | PVC 1Gi per configurazione e chiavi WireGuard |
| `wireguard-deployment.yml` | Deployment `wg-easy:latest`, porte 51820 (UDP VPN) + 51821 (TCP Web UI), nodo light, `NET_ADMIN` + `SYS_MODULE` capabilities, 50m/64Mi req, 200m/128Mi limits |
| `wireguard-service.yml` | Service NodePort: UDP 51820 → NodePort 31820 (VPN) + ClusterIP TCP 51821 (Web UI) |
| `wireguard-ingressroute.yml` | IngressRoute Traefik Host-based `vpn.oci.santocaruso.eu` verso `wireguard:51821`, con middleware `google-auth` (OAuth2 Proxy) |
| `kustomization.yml` | Risorse kustomize |

## Prerequisiti

- Namespace `wireguard` esistente:
  ```bash
  kubectl create namespace wireguard
  ```
- ConfigMap `wireguard-config` con IP pubblico del nodo K8s:
  ```bash
  kubectl create configmap wireguard-config \
    --namespace wireguard \
    --from-literal=WG_HOST=<IP_PUBBLICO_NODO>
  ```
- Secret `wireguard-secret` con password hash bcrypt per Web UI:
  ```bash
  # Genera hash bcrypt della password
  docker run -it ghcr.io/wg-easy/wg-easy wgpw 'LA_TUA_PASSWORD'

  kubectl create secret generic wireguard-secret \
    --namespace wireguard \
    --from-literal=PASSWORD_HASH='<HASH_BCRYPT>'
  ```
- Regola firewall UDP 31820 aperta (Terraform `network.tf` su `oke-node-sl`)
- Traefik Ingress Controller installato con middleware `google-auth` nel namespace `traefik`
- DNS A record: `vpn.oci.santocaruso.eu` verso IP pubblico nodo K8s

## Installazione

```bash
# Applica i manifest
kubectl apply -k infrastructures/OCI/k8s/wireguard/

# Verifica
kubectl rollout status deployment wireguard --namespace wireguard --timeout=120s
kubectl get pods -n wireguard -l app=wireguard
kubectl get ingressroute -n wireguard
```

## Accesso Web UI

Dopo l'applicazione della IngressRoute, la Web UI e' raggiungibile su:

```
https://vpn.oci.santocaruso.eu
```

L'accesso richiede autenticazione Google SSO (OAuth2 Proxy) + password bcrypt nativa wg-easy.

## Configurazione Client

1. Accedere alla Web UI e creare un nuovo peer
2. Scaricare il file di configurazione `.conf` o scansionare il QR code
3. Importare nel client WireGuard (disponibile per Windows, macOS, Linux, iOS, Android)

## Verifica connessione VPN

Dopo la connessione VPN, i servizi interni del cluster sono raggiungibili:

```bash
# PostgreSQL
psql -h postgres.database.svc.cluster.local -p 5432 -U events

# Redis
redis-cli -h redis.database.svc.cluster.local -a <password>

# Backoffice API
curl http://backoffice.events.svc.cluster.local:8000/api/version/

# Prometheus
curl http://prometheus-server.monitoring.svc:80
```

## Connessione interna

```
wireguard.wireguard.svc:51821
```

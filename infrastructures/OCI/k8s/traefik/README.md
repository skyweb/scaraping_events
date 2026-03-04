# Traefik Ingress Controller

Ingress controller per il cluster OKE con TLS automatico (Let's Encrypt ACME).

## File

| File | Contenuto |
|---|---|
| `traefik-values-base.yml` | Helm values: NodePort, nodo light, senza ACME |
| `traefik-values-acme.yml` | Helm values: ACME HTTPS + hostPort (accesso diretto) |
| `traefik-values-reverse-proxy.yml` | Helm values: ACME + reverse proxy TCP da micro-gw |
| `traefik-dashboard-ingressroute.yml` | IngressRoute Traefik Dashboard `traefik.oci.santocaruso.eu` con OAuth2 |

## Prerequisiti

- Namespace `traefik` esistente:
  ```bash
  kubectl create namespace traefik
  ```
- Helm repo:
  ```bash
  helm repo add traefik https://traefik.github.io/charts
  helm repo update
  ```
- DNS A record: `traefik.oci.santocaruso.eu` verso IP pubblico

## Installazione

Tre modalità in base all'architettura:

### Base (senza ACME)
```bash
helm upgrade --install traefik traefik/traefik \
  --namespace traefik \
  -f traefik-values-base.yml \
  --set ports.web.nodePort=30080 \
  --set ports.websecure.nodePort=30443 \
  --set ports.traefik.nodePort=30090
```

### ACME HTTPS (accesso diretto, senza reverse proxy)
```bash
helm upgrade --install traefik traefik/traefik \
  --namespace traefik \
  -f traefik-values-acme.yml \
  --set ports.web.nodePort=30080 \
  --set ports.websecure.nodePort=30443 \
  --set ports.traefik.nodePort=30090 \
  --set "certificatesResolvers.letsencrypt.acme.email=YOUR_EMAIL" \
  --set "certificatesResolvers.letsencrypt.acme.storage=/data/acme.json" \
  --set "certificatesResolvers.letsencrypt.acme.httpChallenge.entryPoint=web"
```

### Reverse Proxy (TCP forwarding da micro-gw)
```bash
helm upgrade --install traefik traefik/traefik \
  --namespace traefik \
  -f traefik-values-reverse-proxy.yml \
  --set ports.web.nodePort=30080 \
  --set ports.websecure.nodePort=30443 \
  --set ports.traefik.nodePort=30090 \
  --set "certificatesResolvers.letsencrypt.acme.email=YOUR_EMAIL" \
  --set "certificatesResolvers.letsencrypt.acme.storage=/data/acme.json" \
  --set "certificatesResolvers.letsencrypt.acme.httpChallenge.entryPoint=web"
```

### IngressRoute Dashboard
```bash
kubectl apply -k infrastructures/OCI/k8s/traefik/
```

## Verifica

```bash
kubectl rollout status deployment traefik --namespace traefik --timeout=120s
kubectl get svc -n traefik
kubectl get ingressroute -n traefik
```

## Accesso Dashboard

```
https://traefik.oci.santocaruso.eu
```

Protetto da OAuth2 Proxy (Google SSO).

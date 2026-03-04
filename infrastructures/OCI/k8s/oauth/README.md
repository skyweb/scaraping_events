# OAuth2 Proxy (Google SSO)

Autenticazione centralizzata per servizi K8s senza auth nativa.
Usa Google come identity provider via OAuth2 Proxy + Traefik ForwardAuth middleware.

## File

| File | Contenuto |
|---|---|
| `oauth2-proxy-deployment.yml` | Deployment OAuth2 Proxy, credenziali da Secret `oauth2-proxy-secret` |
| `oauth2-proxy-service.yml` | Service ClusterIP porta 4180 |
| `oauth2-proxy-middleware.yml` | Traefik Middleware ForwardAuth `google-auth` |
| `oauth2-proxy-auth-ingressroute.yml` | IngressRoute `auth.oci.santocaruso.eu` (callback Google) |
| `oauth2-proxy-catchall-ingressroute.yml` | IngressRoute catch-all `/oauth2/` (sign-in su qualsiasi host) |

## Prerequisiti

- Traefik installato nel cluster
- Google Cloud Console: Credentials > OAuth 2.0 Client ID (tipo: Web application)
- Authorized redirect URI: `https://auth.oci.santocaruso.eu/oauth2/callback`
- Secret con credenziali:
  ```bash
  kubectl create secret generic oauth2-proxy-secret --namespace traefik \
    --from-literal=client-id=<GOOGLE_CLIENT_ID> \
    --from-literal=client-secret=<GOOGLE_CLIENT_SECRET> \
    --from-literal=cookie-secret=<COOKIE_SECRET>
  ```
- ConfigMap con email autorizzate:
  ```bash
  kubectl create configmap oauth2-proxy-emails --namespace traefik \
    --from-literal=allowed-emails.txt="email1@example.com
  email2@example.com"
  ```
- DNS A record: `auth.oci.santocaruso.eu` verso IP pubblico

## Installazione

```bash
kubectl apply -k infrastructures/OCI/k8s/oauth/

# Verifica
kubectl rollout status deployment oauth2-proxy --namespace traefik --timeout=120s
kubectl get middleware -n traefik
kubectl get ingressroute -n traefik
```

## Utilizzo

I servizi protetti aggiungono il middleware nella loro IngressRoute:

```yaml
middlewares:
  - name: google-auth
    namespace: traefik
```

Servizi attualmente protetti: Traefik Dashboard, Prometheus, Alertmanager, Loki, K8s Dashboard, Velero UI, WireGuard.

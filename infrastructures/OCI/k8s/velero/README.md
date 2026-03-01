# Velero UI

Interfaccia web per gestione backup Velero, namespace `velero`, nodo heavy.

## File

| File | Contenuto |
|---|---|
| `velero-ui-serviceaccount.yml` | ServiceAccount `velero-ui` |
| `velero-ui-rbac.yml` | ClusterRole + ClusterRoleBinding + Role + RoleBinding: accesso a namespace, risorse velero.io, pods, secrets, configmaps |
| `velero-ui-configmap.yml` | ConfigMap con policy Casbin (`g,*,manage,all`) |
| `velero-ui-deployment.yml` | Deployment `velero-ui:latest`, porta 3000, nodo heavy, 50m/128Mi req, 200m/256Mi limits, BasicAuth da Secret, readiness/liveness su `/health` |
| `velero-ui-service.yml` | Service ClusterIP porta 80 → targetPort 3000 |
| `velero-ui-ingressroute.yml` | IngressRoute Traefik Host-based `velero.oci.santocaruso.eu` verso `velero-ui:80`, con middleware `google-auth` (OAuth2 Proxy) |

## Prerequisiti

- Namespace `velero` esistente:
  ```bash
  kubectl create namespace velero
  ```
- Velero installato nel cluster
- Secret `velero-ui-secret` con chiave `BASIC_AUTH_PASSWORD`:
  ```bash
  kubectl create secret generic velero-ui-secret \
    --namespace velero \
    --from-literal=BASIC_AUTH_PASSWORD=<PASSWORD>
  ```
- Traefik Ingress Controller installato con middleware `google-auth` nel namespace `traefik`
- DNS A record: `velero.oci.santocaruso.eu` verso IP pubblico

## Installazione

```bash
# Applica i manifest
kubectl apply -k infrastructures/OCI/k8s/velero/

# Verifica
kubectl rollout status deployment velero-ui --namespace velero --timeout=120s
kubectl get pods -n velero -l app=velero-ui
kubectl get ingressroute -n velero
```

## Accesso

Dopo l'applicazione della IngressRoute, il servizio e' raggiungibile su:

```
https://velero.oci.santocaruso.eu
```

L'accesso richiede autenticazione Google SSO (OAuth2 Proxy) + BasicAuth nativo Velero UI.

## Connessione interna

```
velero-ui.velero.svc:80
```

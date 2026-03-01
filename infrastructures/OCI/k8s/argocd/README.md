# ArgoCD (GitOps)

IngressRoute Traefik per ArgoCD, namespace `argocd`.

## File

| File | Contenuto |
|---|---|
| `argocd-ingressroute.yml` | IngressRoute Traefik Host-based `argocd.oci.santocaruso.eu` verso `argocd-server:80`, no auth middleware (auth nativa ArgoCD) |

## Prerequisiti

- Namespace `argocd` esistente:
  ```bash
  kubectl create namespace argocd
  ```
- ArgoCD installato via Helm:
  ```bash
  helm repo add argo https://argoproj.github.io/argo-helm
  helm upgrade --install argocd argo/argo-cd \
    --namespace argocd \
    --set global.nodeSelector.workload=light \
    --set "configs.params.server\.insecure=true" \
    --set server.service.type=ClusterIP \
    --set dex.enabled=false \
    --set notifications.enabled=false \
    --set applicationSet.enabled=false
  ```
- Traefik Ingress Controller installato
- DNS A record: `argocd.oci.santocaruso.eu` verso IP pubblico

## Installazione

```bash
# Applica i manifest (IngressRoute)
kubectl apply -k infrastructures/OCI/k8s/argocd/

# Verifica
kubectl rollout status deployment argocd-server --namespace argocd --timeout=180s
kubectl get ingressroute -n argocd
```

## Accesso

Dopo l'applicazione della IngressRoute, il servizio e' raggiungibile su:

```
https://argocd.oci.santocaruso.eu
```

Password admin iniziale:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
```

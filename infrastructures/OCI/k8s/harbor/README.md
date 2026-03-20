# Harbor (Docker Registry)

Registry privato con UI, vulnerability scanning (Trivy), RBAC, OIDC (Keycloak), image signing (Cosign).

## File

| File | Descrizione |
|------|-------------|
| `harbor-values.yml` | Helm values: PostgreSQL/Redis esterni, persistence, Trivy, metriche |
| `harbor-apisix-route.yml` | ApisixRoute `registry.oci.santocaruso.eu` verso Harbor service |
| `kustomization.yml` | Kustomize per applicare le route |

## Prerequisiti

- Database `harbor` su PostgreSQL condiviso
- Redis condiviso (db index 5-8)
- Secret `harbor-secret` nel namespace `devs`
- DNS A record: `registry.oci.santocaruso.eu`

## Installazione

```bash
# Helm
helm repo add harbor https://helm.goharbor.io
helm repo update

# Secret (credenziali)
kubectl create secret generic harbor-secret --namespace devs \
  --from-literal=admin-password=<HARBOR_ADMIN_PASSWORD> \
  --from-literal=postgres-password=<HARBOR_POSTGRES_PASSWORD> \
  --from-literal=redis-password=<REDIS_PASSWORD> \
  --from-literal=oidc-client-secret=<HARBOR_OIDC_CLIENT_SECRET>

# Installa Harbor
helm upgrade --install harbor harbor/harbor \
  -n devs -f harbor-values.yml

# Route APISIX
kubectl apply -k .

# Attendi ready
kubectl rollout status deployment harbor-core --namespace devs --timeout=300s
```

## Container Registry: Harbor vs OCIR

Il progetto supporta due registry per le immagini Docker:

### Harbor (self-hosted)

Registry interno con UI completa, vulnerability scanning e OIDC.

```bash
# Login
docker login registry.oci.santocaruso.eu

# Push
docker build -t registry.oci.santocaruso.eu/today-events/scraping-service:latest .
docker push registry.oci.santocaruso.eu/today-events/scraping-service:latest

# Firma (Cosign)
cosign sign --key cosign.key registry.oci.santocaruso.eu/today-events/scraping-service:latest

# Pull in K8s (imagePullSecret harbor-robot)
kubectl create secret docker-registry harbor-robot --namespace scraping \
  --docker-server=registry.oci.santocaruso.eu \
  --docker-username=robot\$ci-push \
  --docker-password=<ROBOT_SECRET>
```

### OCIR (Oracle Cloud Infrastructure Registry)

Registry managed Oracle, integrato con OKE.

```bash
# Login (usa Auth Token da OCI Console)
docker login eu-milan-1.ocir.io -u <NAMESPACE>/<EMAIL>

# Push
docker build -t eu-milan-1.ocir.io/<NAMESPACE>/events/scraping-service:latest .
docker push eu-milan-1.ocir.io/<NAMESPACE>/events/scraping-service:latest

# Pull in K8s (imagePullSecret ocir-secret, creato da post-cluster-setup)
# Le immagini usano il path OCIR configurato in oke.yml:
#   scraping_image: "eu-milan-1.ocir.io/<NAMESPACE>/events/scraping:latest"
```

### Configurazione immagine Scrapy

In `oke.yml` configurare il registry desiderato:

```yaml
# Harbor (self-hosted)
scraping_image: "registry.oci.santocaruso.eu/today-events/scraping-service:latest"

# OCIR (Oracle managed)
scraping_image: "eu-milan-1.ocir.io/<NAMESPACE>/events/scraping:latest"
```

## Configurazione OIDC (post-installazione)

Dopo l'installazione, configurare OIDC via API Harbor:

```bash
curl -X PUT -u "admin:<PASSWORD>" \
  -H "Content-Type: application/json" \
  "https://registry.oci.santocaruso.eu/api/v2.0/configurations" \
  -d '{
    "auth_mode": "oidc_auth",
    "oidc_name": "Keycloak",
    "oidc_endpoint": "https://auth.oci.santocaruso.eu/realms/today-events",
    "oidc_client_id": "harbor",
    "oidc_client_secret": "<HARBOR_OIDC_CLIENT_SECRET>",
    "oidc_scope": "openid,profile,email",
    "oidc_verify_cert": true,
    "oidc_auto_onboard": true,
    "oidc_user_claim": "email",
    "oidc_groups_claim": "groups",
    "oidc_admin_group": "harbor-admins"
  }'
```

## Accesso

| URL | Credenziali |
|-----|-------------|
| `https://registry.oci.santocaruso.eu` | Keycloak SSO oppure admin locale |

# SonarQube (Code Quality & Security)

Analisi statica del codice, code coverage e security scanning.

## File

| File | Contenuto |
|---|---|
| `sonarqube-values.yml` | Helm values: Community edition, PostgreSQL embedded, persistence 5Gi |
| `sonarqube-ingressroute.yml` | IngressRoute Traefik `sonarqube.oci.santocaruso.eu` verso `sonarqube-sonarqube:9000` |

## Prerequisiti

- Namespace `sonarqube` esistente:
  ```bash
  kubectl create namespace sonarqube
  ```
- Secret per admin password:
  ```bash
  kubectl create secret generic sonarqube-secret --namespace sonarqube \
    --from-literal=password=<SONARQUBE_ADMIN_PASSWORD> \
    --from-literal=currentPassword=admin
  ```
- Traefik Ingress Controller installato
- DNS A record: `sonarqube.oci.santocaruso.eu` verso IP pubblico

## Installazione

```bash
# Helm repo
helm repo add sonarqube https://SonarSource.github.io/helm-chart-sonarqube
helm repo update

# Installa SonarQube
helm upgrade --install sonarqube sonarqube/sonarqube \
  -n sonarqube -f sonarqube-values.yml

# Applica IngressRoute
kubectl apply -k infrastructures/OCI/k8s/sonarqube/

# Verifica
kubectl rollout status statefulset sonarqube-sonarqube --namespace sonarqube --timeout=300s
kubectl get ingressroute -n sonarqube
```

## Accesso

```
https://sonarqube.oci.santocaruso.eu
```

- User: `admin`
- Password: valore in `sonarqube-secret`

## Integrazione CI/CD

Per analizzare un progetto, genera un token in SonarQube (My Account > Security > Tokens), poi:

```bash
sonar-scanner \
  -Dsonar.projectKey=<PROJECT_KEY> \
  -Dsonar.host.url=https://sonarqube.oci.santocaruso.eu \
  -Dsonar.token=<TOKEN>
```

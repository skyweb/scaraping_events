# Tekton Pipelines + Kaniko

Pipeline CI/CD cloud-native con Tekton e build immagini via Kaniko, namespace `tekton-pipelines`.

## File

| File | Contenuto |
|---|---|
| `tekton-ingressroute.yml` | IngressRoute Traefik Host-based `tekton.oci.santocaruso.eu` verso `tekton-dashboard:9097` |
| `tekton-serviceaccount.yml` | ServiceAccount `tekton-build` con accesso OCIR (`ocir-secret`) |
| `tekton-task-kaniko-build.yml` | Task Kaniko: build + push immagini Docker con parametri IMAGE, DOCKERFILE, CONTEXT, EXTRA_ARGS |
| `tekton-pipeline-build-and-push.yml` | Pipeline completa: git-clone → kaniko-build con parametri repo-url, revision, image, dockerfile, context |

## Prerequisiti

- Namespace `tekton-pipelines` esistente:
  ```bash
  kubectl create namespace tekton-pipelines
  ```
- Tekton Pipelines + Dashboard installati da release upstream:
  ```bash
  kubectl apply -f https://storage.googleapis.com/tekton-releases/pipeline/previous/v0.65.2/release.yaml
  kubectl apply -f https://github.com/tektoncd/dashboard/releases/download/v0.64.0/release.yaml
  ```
- Task `git-clone` dal catalogo Tekton:
  ```bash
  kubectl apply -f https://raw.githubusercontent.com/tektoncd/catalog/main/task/git-clone/0.9/git-clone.yaml -n tekton-pipelines
  ```
- Secret `ocir-secret` (docker-registry) per push immagini su OCIR:
  ```bash
  kubectl create secret docker-registry ocir-secret \
    --docker-server=eu-milan-1.ocir.io \
    --docker-username=<OCIR_USERNAME> \
    --docker-password=<AUTH_TOKEN> \
    --namespace=tekton-pipelines
  ```
- Traefik Ingress Controller installato
- DNS A record: `tekton.oci.santocaruso.eu` verso IP pubblico

## Installazione

```bash
# Applica i manifest
kubectl apply -k infrastructures/OCI/k8s/tekton/

# Verifica
kubectl get tasks,pipelines -n tekton-pipelines
kubectl get ingressroute -n tekton-pipelines
kubectl get serviceaccount tekton-build -n tekton-pipelines
```

## Accesso

Dopo l'applicazione della IngressRoute, la dashboard e' raggiungibile su:

```
https://tekton.oci.santocaruso.eu
```

## Esempio PipelineRun

```bash
kubectl create -f - <<EOF
apiVersion: tekton.dev/v1
kind: PipelineRun
metadata:
  generateName: build-backoffice-
  namespace: tekton-pipelines
spec:
  pipelineRef:
    name: build-and-push
  params:
    - name: repo-url
      value: "https://github.com/skyweb/scaraping_events.git"
    - name: revision
      value: "main"
    - name: image
      value: "eu-milan-1.ocir.io/axbuakdjv1li/events/backoffice:latest"
    - name: dockerfile
      value: "./services/service-backoffice/Dockerfile"
    - name: context
      value: "./services/service-backoffice"
  workspaces:
    - name: shared-workspace
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources:
            requests:
              storage: 1Gi
  taskRunTemplate:
    serviceAccountName: tekton-build
EOF
```

# NexaBank Demo App

NexaBank is a static-content demo application that simulates a retail banking web portal. It has no backend — all pages are pre-built HTML/CSS/JS served directly by nginx. The app is intended for testing Kubernetes deployments, ingress configurations, autoscaling policies, and front-end tooling pipelines in a safe, non-production environment.

## Pages

| Path | Description |
|---|---|
| `/` | Landing / marketing page |
| `/login.html` | Login form |
| `/dashboard.html` | Account overview |
| `/transactions.html` | Transaction history |
| `/transfer.html` | Fund transfer form |
| `/services.html` | Services catalogue |
| `/loans/` | Loans hub and product pages |

## Repository layout

```
.
├── Dockerfile          # nginx-unprivileged image with static content
├── k8s/
│   ├── base/           # Namespace, Deployment, Service, Ingress, HPA
│   └── overlays/
│       ├── dev/        # 1 replica, :dev image tag
│       └── prod/       # production replica count and image tag
├── css/
├── js/
└── loans/
```

## Local development

Run the app locally with Docker:

```sh
docker build -t nexabank:local .
docker run --rm -p 8080:8080 nexabank:local
```

Then open http://localhost:8080.

## Deploying to a test environment

### Prerequisites

- Docker (with push access to `ghcr.io/drpotters`)
- `kubectl` pointed at your test cluster
- `kustomize` v5+ (or `kubectl` ≥ 1.27 which bundles it)

### Step 1 — Build and push the image

```sh
docker build -t ghcr.io/drpotters/nexabank:dev .
docker push ghcr.io/drpotters/nexabank:dev
```

### Step 2 — Deploy the dev overlay

```sh
kubectl apply -k k8s/overlays/dev
```

This creates the `nexabank` namespace and deploys 1 replica with the `:dev` image tag.

### Step 3 — Verify the rollout

```sh
kubectl -n nexabank get deploy,svc,pods,ingress
kubectl -n nexabank rollout status deploy/nexabank
```

### Step 4 — Access the app

If your cluster has an ingress controller, the app is reachable at the host defined in `k8s/base/ingress.yaml`.

Without an ingress controller, use port-forward:

```sh
kubectl -n nexabank port-forward svc/nexabank 8080:80
```

Then open http://localhost:8080.

### Step 5 — Smoke test

```sh
kubectl -n nexabank run nexabank-smoke --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- \
  curl -fsS http://nexabank/index.html
```

### Tear down

```sh
kubectl delete -k k8s/overlays/dev
```

---

For full details on building, deploying to prod, and all `kubectl` commands, see [README-k8s.md](README-k8s.md).

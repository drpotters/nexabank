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

## Workload introspection endpoints

The image exposes four JSON endpoints useful for verifying which pod served a
request and where the caller came from. Pod/node values are injected via the
Kubernetes Downward API (see `env:` in `k8s/base/deployment.yaml`); outside
Kubernetes they render empty but the endpoints still respond.

| Endpoint       | Purpose                                                        |
| -------------- | -------------------------------------------------------------- |
| `/health`      | Pod health/status (used by liveness & readiness probes).       |
| `/pod-info`    | Pod name, namespace, pod IP, node name, hostname, app/version. |
| `/origin-info` | Caller IP, `X-Forwarded-*` headers, host, scheme, user-agent.  |
| `/whoami`      | Container identity: hostname, pod, node, app/version.          |

The Kubernetes liveness and readiness probes (and the image `HEALTHCHECK`) hit
`/health`, which returns HTTP 200 with `{"status":"ok",...}` while nginx is serving.

Examples:

```sh
kubectl -n nexabank port-forward svc/nexabank 8080:80
curl -s http://localhost:8080/health | jq
curl -s http://localhost:8080/pod-info | jq
curl -s http://localhost:8080/origin-info | jq
curl -s http://localhost:8080/whoami | jq
```

Sample `/pod-info` response:

```json
{
  "pod_name": "nexabank-7c9f8b6d4-abcde",
  "pod_namespace": "nexabank",
  "pod_ip": "10.244.1.23",
  "node_name": "aks-nodepool1-000000-vmss000001",
  "hostname": "nexabank-7c9f8b6d4-abcde",
  "app": "nexabank",
  "version": "latest",
  "server_time": "2026-07-09T01:23:45+00:00"
}
```
The Kubernetes liveness and readiness probes (and the image `HEALTHCHECK`) hit
`/health`, which returns HTTP 200 with `{"status":"ok",...}` while nginx is serving.

Examples:

```sh
kubectl -n nexabank port-forward svc/nexabank 8080:80
curl -s http://localhost:8080/health | jq
curl -s http://localhost:8080/pod-info | jq
curl -s http://localhost:8080/origin-info | jq
curl -s http://localhost:8080/whoami | jq
```

Sample `/pod-info` response:

```json
{
  "pod_name": "nexabank-7c9f8b6d4-abcde",
  "pod_namespace": "nexabank",
  "pod_ip": "10.244.1.23",
  "node_name": "aks-nodepool1-000000-vmss000001",
  "hostname": "nexabank-7c9f8b6d4-abcde",
  "app": "nexabank",
  "version": "latest",
  "server_time": "2026-07-09T01:23:45+00:00"
}
```The Kubernetes liveness and readiness probes (and the image `HEALTHCHECK`) hit
`/health`, which returns HTTP 200 with `{"status":"ok",...}` while nginx is serving.

Examples:

```sh
kubectl -n nexabank port-forward svc/nexabank 8080:80
curl -s http://localhost:8080/health | jq
curl -s http://localhost:8080/pod-info | jq
curl -s http://localhost:8080/origin-info | jq
curl -s http://localhost:8080/whoami | jq
```

Sample `/pod-info` response:

```json
{
  "pod_name": "nexabank-7c9f8b6d4-abcde",
  "pod_namespace": "nexabank",
  "pod_ip": "10.244.1.23",
  "node_name": "aks-nodepool1-000000-vmss000001",
  "hostname": "nexabank-7c9f8b6d4-abcde",
  "app": "nexabank",
  "version": "latest",
  "server_time": "2026-07-09T01:23:45+00:00"
}
```The Kubernetes liveness and readiness probes (and the image `HEALTHCHECK`) hit
`/health`, which returns HTTP 200 with `{"status":"ok",...}` while nginx is serving.

Examples:

```sh
kubectl -n nexabank port-forward svc/nexabank 8080:80
curl -s http://localhost:8080/health | jq
curl -s http://localhost:8080/pod-info | jq
curl -s http://localhost:8080/origin-info | jq
curl -s http://localhost:8080/whoami | jq
```

Sample `/pod-info` response:

```json
{
  "pod_name": "nexabank-7c9f8b6d4-abcde",
  "pod_namespace": "nexabank",
  "pod_ip": "10.244.1.23",
  "node_name": "aks-nodepool1-000000-vmss000001",
  "hostname": "nexabank-7c9f8b6d4-abcde",
  "app": "nexabank",
  "version": "latest",
  "server_time": "2026-07-09T01:23:45+00:00"
}
```The Kubernetes liveness and readiness probes (and the image `HEALTHCHECK`) hit
`/health`, which returns HTTP 200 with `{"status":"ok",...}` while nginx is serving.

Examples:

```sh
kubectl -n nexabank port-forward svc/nexabank 8080:80
curl -s http://localhost:8080/health | jq
curl -s http://localhost:8080/pod-info | jq
curl -s http://localhost:8080/origin-info | jq
curl -s http://localhost:8080/whoami | jq
```

Sample `/pod-info` response:

```json
{
  "pod_name": "nexabank-7c9f8b6d4-abcde",
  "pod_namespace": "nexabank",
  "pod_ip": "10.244.1.23",
  "node_name": "aks-nodepool1-000000-vmss000001",
  "hostname": "nexabank-7c9f8b6d4-abcde",
  "app": "nexabank",
  "version": "latest",
  "server_time": "2026-07-09T01:23:45+00:00"
}
```
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

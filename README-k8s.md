# NexaBank Kubernetes Package

This folder can be packaged as a container image and deployed to Kubernetes using the manifests in `k8s/`.

## 1) Build and push image

Set your registry and tag:

```sh
docker build -t <registry>/nexabank:<tag> .
docker push <registry>/nexabank:<tag>
```

Example:

```sh
docker build -t ghcr.io/drpotters/nexabank:1.0.0 .
docker push ghcr.io/drpotters/nexabank:1.0.0
```

## 2) Deploy with Kustomize (recommended)

### Dev

```sh
kubectl apply -k k8s/overlays/dev
```

### Prod

Edit image in `k8s/overlays/prod/kustomization.yaml`, then:

```sh
kubectl apply -k k8s/overlays/prod
```

## 3) Verify

```sh
kubectl -n nexabank get deploy,svc,pods,ingress
kubectl -n nexabank rollout status deploy/nexabank
```

If no ingress controller is available, use port-forward:

```sh
kubectl -n nexabank port-forward svc/nexabank 8080:80
```

Then open:

- http://localhost:8080

For a quick smoke test against the running service:

```sh
kubectl -n nexabank run nexabank-smoke --rm -it --restart=Never --image=curlimages/curl:8.10.1 -- \
	curl -fsS http://nexabank/index.html
```

## Workload introspection endpoints

The image exposes four JSON endpoints useful for verifying which pod served a
request and where the caller came from. Pod/node values are injected via the
Kubernetes Downward API (see `env:` in `k8s/base/deployment.yaml`); outside
Kubernetes they render empty but the endpoints still respond.

| Endpoint       | Purpose                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------ |
| `/health`      | Pod health/status (used by liveness & readiness probes).                                   |
| `/pod-info`    | Pod name, namespace, pod IP, node name, hostname, app/version.                             |
| `/origin-info` | Caller IP, `X-Forwarded-*` headers, host, scheme, user-agent, plus serving pod/node/platform. |
| `/whoami`      | Container identity: hostname, pod, node, app/version.                                      |

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

Sample `/origin-info` response:

```json
{
  "client_ip": "10.244.0.7",
  "x_forwarded_for": "203.0.113.42",
  "x_forwarded_proto": "https",
  "x_real_ip": "203.0.113.42",
  "host": "nexabank.example.com",
  "scheme": "http",
  "request_method": "GET",
  "uri": "/origin-info",
  "user_agent": "curl/8.10.1",
  "pod_name": "nexabank-7c9f8b6d4-abcde",
  "pod_namespace": "nexabank",
  "pod_ip": "10.244.1.23",
  "node_name": "ip-10-0-12-34.us-west-2.compute.internal",
  "host_provider": "aws",
  "server_time": "2026-07-09T01:23:45+00:00"
}
```

### Identifying the host platform (`host_provider`)

`/origin-info` reports a `host_provider` field so you can tell which platform a
pod is running on when the same image is deployed across multiple clusters. It is
driven by the `HOST_PROVIDER` environment variable, which defaults to `unknown`
in `k8s/base/deployment.yaml`.

Ready-made overlays are provided for each platform:

```sh
kubectl apply -k k8s/overlays/eks     # host_provider="aws"
kubectl apply -k k8s/overlays/gke     # host_provider="gcp"
kubectl apply -k k8s/overlays/vmware  # host_provider="vmware"
```

These are thin overlays over `k8s/base` that pull in a reusable Kustomize
component from `k8s/components/provider-*`. The `dev` and `prod` overlays are
platform-agnostic and therefore still report `unknown`; add a component to them
if you want a concrete value:

```yaml
# k8s/overlays/prod/kustomization.yaml
components:
  - ../../components/provider-aws
```

Verify what an overlay will render before applying:

```sh
kubectl kustomize k8s/overlays/gke | grep -A1 HOST_PROVIDER
```

You can also override it ad hoc without editing manifests:

```sh
kubectl -n nexabank set env deploy/nexabank HOST_PROVIDER=gcp
```

To add a platform not covered above (e.g. `azure`, `onprem`, `local`), copy one
of the `k8s/components/provider-*` directories and change the `value:`.

## Notes

- Static content is served by `nginxinc/nginx-unprivileged:1.27-alpine` on container port `8080`.
- Introspection endpoints are configured in `nginx/templates/default.conf.template`, rendered at startup via the image's `envsubst` templating.
- Kubernetes base includes: Namespace, Deployment, Service, Ingress, and HorizontalPodAutoscaler.
- Overlays provide env-specific image tags and replica counts.

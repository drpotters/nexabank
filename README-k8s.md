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

## Notes

- Static content is served by `nginxinc/nginx-unprivileged:1.27-alpine` on container port `8080`.
- Kubernetes base includes: Namespace, Deployment, Service, Ingress, and HorizontalPodAutoscaler.
- Overlays provide env-specific image tags and replica counts.

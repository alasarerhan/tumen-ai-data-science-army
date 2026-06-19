# platform — Helm Chart

Deploys the **Platform API** FastAPI service and (optionally) a bundled
development PostgreSQL instance onto a Kubernetes cluster.

---

## Quick Start

```bash
# Add / update a values override file (never commit secrets to git)
cat > my-values.yaml <<EOF
image:
  tag: "0.1.0"

config:
  AUTH_MODE: "oidc"
  OIDC_ISSUER: "https://your-issuer.example.com"
  OIDC_AUDIENCE: "your-audience"
  OIDC_JWKS_URL: "https://your-issuer.example.com/.well-known/jwks.json"

db:
  host: "my-postgres.example.com"
  name: "platform"
  user: "platform"
  existingSecret: "platform-db-secret"   # pre-created K8s Secret
  existingSecretKey: "POSTGRES_PASSWORD"

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: api.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: api-tls
      hosts:
        - api.example.com
EOF

# Install
helm install platform ./helm/platform -f my-values.yaml

# Upgrade
helm upgrade platform ./helm/platform -f my-values.yaml
```

---

## Development / CI (bundled Postgres)

For local K8s (e.g. kind, k3d) or CI pipelines:

```bash
helm install platform ./helm/platform \
  --set postgres.enabled=true \
  --set db.host=release-platform-postgres \
  --set config.DEPLOYMENT_PROFILE=local \
  --set config.AUTH_MODE=dev \
  --set image.tag=latest
```

> **Warning** — `postgres.enabled=true` deploys a single-pod, non-HA
> Postgres with a `PersistentVolumeClaim`.  **Do not use in production.**

---

## Configuration Reference

### `image`

| Key | Default | Description |
|-----|---------|-------------|
| `image.repository` | `ghcr.io/ai-datascience-team/platform-api` | Container image repository |
| `image.tag` | `""` (uses `appVersion`) | Image tag |
| `image.pullPolicy` | `IfNotPresent` | Pull policy |

### `config` (ConfigMap)

| Key | Default | Description |
|-----|---------|-------------|
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | Bind port |
| `DEPLOYMENT_PROFILE` | `release` | `local` or `release` |
| `AUTH_MODE` | `oidc` | `dev` or `oidc` |
| `OIDC_ISSUER` | `https://accounts.google.com` | OIDC issuer URL |
| `OIDC_AUDIENCE` | `""` | OIDC audience claim |
| `OIDC_JWKS_URL` | `""` | OIDC JWKS endpoint |
| `TENANT_WRITE_QUOTA_PER_MINUTE` | `120` | Write quota per tenant/minute |

### `db` (Database)

| Key | Default | Description |
|-----|---------|-------------|
| `db.host` | `postgres` | PostgreSQL hostname |
| `db.port` | `5432` | PostgreSQL port |
| `db.name` | `platform` | Database name |
| `db.user` | `platform` | Database user |
| `db.existingSecret` | `""` | Name of existing K8s Secret with DB password |
| `db.existingSecretKey` | `POSTGRES_PASSWORD` | Key inside the Secret |
| `db.password` | `""` | Required only when `db.existingSecret` is empty and `postgres.enabled=false`; weak defaults are rejected |

When `db.existingSecret` is empty, a `Secret` named `<release>-db` is
created automatically from `db.password`. The chart fails rendering if
`db.password` is empty or a weak default such as `changeme`, `postgres`, or
`password`. Use `db.existingSecret` for production.

When `postgres.enabled=true`, set `postgres.password` to a non-default value.
The bundled PostgreSQL deployment is for development/CI only and also rejects
empty or weak password defaults.

### `autoscaling`

| Key | Default | Description |
|-----|---------|-------------|
| `autoscaling.enabled` | `false` | Enable HorizontalPodAutoscaler |
| `autoscaling.minReplicas` | `2` | Minimum replicas |
| `autoscaling.maxReplicas` | `10` | Maximum replicas |
| `autoscaling.targetCPUUtilizationPercentage` | `80` | CPU HPA target |
| `autoscaling.targetMemoryUtilizationPercentage` | `80` | Memory HPA target |

### `ingress`

| Key | Default | Description |
|-----|---------|-------------|
| `ingress.enabled` | `false` | Enable Ingress |
| `ingress.className` | `nginx` | IngressClass name |
| `ingress.hosts` | `[{host: platform-api.example.com, ...}]` | Host rules |
| `ingress.tls` | `[]` | TLS configuration |

---

## Prometheus Metrics

The Deployment pods are annotated with:
```yaml
prometheus.io/scrape: "true"
prometheus.io/path: "/metrics"
prometheus.io/port: "8000"
```

The `/metrics` endpoint exposes:
- `platform_api_http_requests_total{method, path, status}` — Counter
- `platform_api_http_request_duration_seconds{method, path}` — Histogram
- `platform_api_http_requests_in_flight` — Gauge

SLO targets (documented in `platform_api/core/observability.py`):
- p99 latency < 500 ms
- error rate < 1 %
- availability > 99.5 %

---

## Health Checks

| Probe | Path | Notes |
|-------|------|-------|
| Liveness | `GET /healthz` | Restarts unhealthy pods |
| Readiness | `GET /healthz` | Gates traffic routing |

---

## Template Files

| File | Description |
|------|-------------|
| `deployment.yaml` | Main FastAPI API server |
| `service.yaml` | ClusterIP Service on port 80 → 8000 |
| `ingress.yaml` | Nginx Ingress (disabled by default) |
| `configmap.yaml` | Non-sensitive environment variables |
| `secret-db.yaml` | DB password Secret (skipped if existingSecret set) |
| `serviceaccount.yaml` | Dedicated ServiceAccount |
| `hpa.yaml` | HorizontalPodAutoscaler (disabled by default) |
| `postgres.yaml` | Bundled dev Postgres (disabled by default) |
| `_helpers.tpl` | Template helper functions |

---

## Air-Gapped / Enterprise Internal Installation (M15 TG3)

This section describes how to deploy the chart in restricted environments with no direct internet egress.

### 1) Mirror images into private registry

1. Pull required images from a connected host:
   - `ghcr.io/ai-datascience-team/platform-api:<tag>`
   - Optional bundled DB image if `postgres.enabled=true`
2. Retag and push to internal registry:

```bash
docker pull ghcr.io/ai-datascience-team/platform-api:0.1.0
docker tag ghcr.io/ai-datascience-team/platform-api:0.1.0 registry.internal.example.com/platform/platform-api:0.1.0
docker push registry.internal.example.com/platform/platform-api:0.1.0
```

3. Set values:

```yaml
image:
  repository: registry.internal.example.com/platform/platform-api
  tag: "0.1.0"
```

### 2) Configure image pull secret

Create secret in target namespace:

```bash
kubectl create secret docker-registry platform-registry \
  --docker-server=registry.internal.example.com \
  --docker-username=<user> \
  --docker-password=<password> \
  --docker-email=<email> \
  -n <namespace>
```

Then reference in values:

```yaml
imagePullSecrets:
  - name: platform-registry
```

### 3) Offline chart packaging

From a connected build host:

```bash
helm dependency build ./helm/platform
helm package ./helm/platform --destination ./dist
```

Copy `dist/platform-<version>.tgz` and your `values-airgap.yaml` to the offline environment, then install:

```bash
helm upgrade --install platform ./platform-<version>.tgz -f values-airgap.yaml -n <namespace>
```

### 4) Secret management policy

- Do not store secrets in `values.yaml` or git.
- Use pre-created Kubernetes Secrets (`db.existingSecret`) and external secret injection for OIDC/API keys.
- Rotate DB and OIDC secrets on a fixed cadence.

### 5) Upgrade / rollback in restricted clusters

Upgrade:

```bash
helm upgrade platform ./platform-<version>.tgz -f values-airgap.yaml -n <namespace>
```

Rollback to previous healthy revision:

```bash
helm history platform -n <namespace>
helm rollback platform <revision> -n <namespace>
```

### 6) Validation checklist (offline)

- `kubectl get pods` shows Ready replicas.
- `kubectl get events` has no image pull errors.
- `/healthz` responds through cluster ingress/service.
- App can connect to internal Postgres/Cloud SQL proxy.
- OIDC/JWKS endpoints are reachable through approved internal path.

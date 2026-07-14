# Deployment Guide

This document covers all deployment scenarios for IMPACT: publishing to PyPI,
running with Docker, and deploying the distributed crawler on Kubernetes.

---

## 1. Publishing to PyPI

### One-time PyPI setup (Trusted Publisher)

IMPACT uses [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
(OIDC) for automated publishing. No API token or secret is stored in GitHub —
the handshake is handled entirely between GitHub Actions and PyPI.

Because `impact-core` does not yet exist on PyPI, use the **Pending Publisher**
flow:

1. **Create a PyPI account** (if you don't have one):
   https://pypi.org/account/register/

2. **Enable 2FA** — required by PyPI for all publishers:
   https://pypi.org/manage/account/#two-factor

3. **Register a Pending Publisher**:
   https://pypi.org/manage/account/publishing/

   Fill in the form under *"Add a new pending publisher"*:

   | Field | Value |
   |-------|-------|
   | PyPI Project Name | `impact-core` |
   | Owner | your GitHub username or org (e.g. `KathiraveluLab`) |
   | Repository name | `IMPACT` |
   | Workflow filename | `publish.yml` |
   | Environment name | `pypi` |

   Click **Add**.

4. **Create the `pypi` environment in GitHub**:
   - Go to your repo → **Settings → Environments → New environment**
   - Name it exactly `pypi`
   - No secrets or protection rules are required

After the first successful publish the pending publisher automatically converts
to a regular project-level trusted publisher.

---

### Releasing a new version

1. Bump `version` in `pyproject.toml`:
   ```toml
   [project]
   version = "1.0.1"
   ```

2. Commit and push:
   ```bash
   git add pyproject.toml
   git commit -m "chore: bump version to 1.0.1"
   git push
   ```

3. Push a version tag:
   ```bash
   git tag v1.0.1
   git push origin v1.0.1
   ```

The `.github/workflows/publish.yml` workflow triggers automatically, builds the
wheel and source distribution, and publishes them to PyPI. No further action
needed.

> **Tag format:** tags must start with `v` (e.g. `v1.0.0`, `v1.0.1`).
> Any other tag format is ignored by the workflow.

---

### Building locally (without publishing)

```bash
pip install build
python -m build          # produces dist/impact_core-*.whl and .tar.gz
```

To verify the package before uploading:
```bash
pip install twine
twine check dist/*
```

---

## 2. Docker (single-node crawler)

### Build the image

```bash
docker build -t impact-crawler:latest .
```

### Run discovery (populate the queue)

```bash
docker run --rm \
  -e GITHUB_TOKEN=ghp_yourtoken \
  -v "$(pwd)/test_projects:/app/test_projects" \
  impact-crawler:latest discover --min-stars 1000
```

### Run the crawler

```bash
docker run --rm \
  -v "$(pwd)/test_projects:/app/test_projects" \
  impact-crawler:latest crawl --limit 50
```

The SQLite queue database is written inside the mounted volume at
`test_projects/github_benchmarks/crawler_queue.db`.

---

## 3. Kubernetes (multi-node distributed crawler)

Multiple crawler worker pods coordinate on a shared PostgreSQL queue.
Each pod atomically claims one repository at a time using
`SELECT FOR UPDATE SKIP LOCKED`, so no two pods process the same repository.

### Prerequisites

- A running Kubernetes cluster (local: [minikube](https://minikube.sigs.k8s.io/)
  or [kind](https://kind.sigs.k8s.io/))
- `kubectl` configured to point at it
- The `impact-crawler:latest` image built and available in the cluster

### Step 1 — Create the namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### Step 2 — Create the database secret

> **Security:** `k8s/secret.yaml` is listed in `.gitignore` and must never be
> committed to the repository. Only `k8s/secret.yaml.example` (with placeholder
> values) is tracked in git.

**Option A — imperative (recommended, nothing touches disk):**
```bash
kubectl create secret generic postgres-secret \
  --from-literal=username=impact \
  --from-literal=password=yourpassword \
  -n impact-crawler
```

**Option B — file-based (stays local, gitignored):**
```bash
cp k8s/secret.yaml.example k8s/secret.yaml
# Edit k8s/secret.yaml — replace placeholder values with real base64 strings:
#   echo -n 'impact'      | base64   → username value
#   echo -n 'yourpassword' | base64  → password value
kubectl apply -f k8s/secret.yaml
```

### Step 3 — Deploy PostgreSQL and configuration

```bash
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/postgres.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres \
  -n impact-crawler --timeout=60s
```

### Step 4 — Run the discovery Job

```bash
kubectl apply -f k8s/discovery-job.yaml
kubectl wait --for=condition=complete job/crawler-discovery \
  -n impact-crawler --timeout=300s
```

### Step 5 — Start the crawler workers

```bash
kubectl apply -f k8s/crawler-deployment.yaml
```

This starts **4 parallel worker pods** by default. Watch logs:

```bash
kubectl logs -l role=worker -n impact-crawler --follow
```

### Applying everything at once (after the secret exists)

```bash
kubectl apply -k k8s/
```

### Scaling workers

```bash
kubectl scale deployment crawler-worker --replicas=8 -n impact-crawler
```

### Tearing everything down

```bash
kubectl delete namespace impact-crawler
```

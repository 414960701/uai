# Kubernetes example

These manifests demonstrate the `0.1.x` single-node deployment shape. They are
not a distributed or highly available installation.

## SQLite and runtime limits

- The backend must remain at exactly **one replica**. SQLite, live event fan-out,
  concurrency gates, and running tasks are process-local in this release.
- The backend uses a `ReadWriteOnce` PVC and a `Recreate` deployment strategy.
  Do not place the database on a multi-writer network filesystem.
- A restarted process does not resume an interrupted Run. Inspect any Run left
  in `running` state after a restart.
- OIDC/RBAC, durable queues, checkpoint recovery, and production-grade tenant
  isolation are not implemented in `0.1.x`.

## Apply the sample

1. Build and push both images, then replace `ghcr.io/your-org/...` in the
   deployments.
2. Replace the example CORS origin in `configmap.yaml`.
3. Optionally create the referenced control credential without writing it into
   a manifest:

   ```bash
   kubectl -n uai-forge create secret generic uai-forge-control \
     --from-literal=control-api-key='<generated-value>'
   ```

4. Apply the core resources:

   ```bash
   kubectl apply -k deploy/kubernetes
   ```

5. For local verification, forward both services:

   ```bash
   kubectl -n uai-forge port-forward service/uai-forge-frontend 3000:3000
   kubectl -n uai-forge port-forward service/uai-forge-backend 8000:8000
   ```

For ingress-based use, customize and apply `ingress.example.yaml`, configure TLS,
and set the control center API address to the public HTTPS backend URL. The
browser cannot reach the in-cluster service DNS name directly.

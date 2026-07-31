#!/usr/bin/env bash
set -euo pipefail

allocate_loopback_port() {
  python3 - <<'PY'
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
    listener.bind(("127.0.0.1", 0))
    print(listener.getsockname()[1])
PY
}

SMOKE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SMOKE_ROOT="$(cd "$SMOKE_SCRIPT_DIR/.." && pwd)"
SMOKE_SUFFIX="${UAI_FORGE_SMOKE_SUFFIX:-$(date -u +%Y%m%d%H%M%S)-$$}"
SMOKE_PROJECT="${UAI_FORGE_SMOKE_PROJECT:-uai-forge-smoke-${SMOKE_SUFFIX}}"
SMOKE_VOLUME="${UAI_FORGE_SMOKE_VOLUME:-uai-forge-smoke-data-${SMOKE_SUFFIX}}"
SMOKE_NETWORK="${SMOKE_PROJECT}_default"
SMOKE_BACKEND_IMAGE="${SMOKE_PROJECT}-backend:smoke"
SMOKE_FRONTEND_IMAGE="${SMOKE_PROJECT}-frontend:smoke"
SMOKE_API_PORT="${UAI_FORGE_SMOKE_API_PORT:-$(allocate_loopback_port)}"
SMOKE_WEB_PORT="${UAI_FORGE_SMOKE_WEB_PORT:-$(allocate_loopback_port)}"
while [[ "$SMOKE_WEB_PORT" == "$SMOKE_API_PORT" && -z "${UAI_FORGE_SMOKE_WEB_PORT:-}" ]]; do
  SMOKE_WEB_PORT="$(allocate_loopback_port)"
done
if [[ "$SMOKE_WEB_PORT" == "$SMOKE_API_PORT" ]]; then
  echo "API and Web smoke ports must be different: ${SMOKE_API_PORT}" >&2
  exit 1
fi
if [[ ! "$SMOKE_PROJECT" =~ ^[a-z0-9][a-z0-9_-]*$ ]]; then
  echo "Unsafe smoke project name: ${SMOKE_PROJECT}" >&2
  exit 1
fi
if [[ "${#SMOKE_PROJECT}" -gt 63 ]]; then
  echo "Smoke project name is too long: ${SMOKE_PROJECT}" >&2
  exit 1
fi
if [[ ! "$SMOKE_VOLUME" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]]; then
  echo "Unsafe smoke volume name: ${SMOKE_VOLUME}" >&2
  exit 1
fi
if [[ -n "$(docker ps --all --quiet --filter "label=com.docker.compose.project=${SMOKE_PROJECT}")" ]]; then
  echo "Refusing to reuse an existing Compose project: ${SMOKE_PROJECT}" >&2
  exit 1
fi
if docker network inspect "$SMOKE_NETWORK" >/dev/null 2>&1; then
  echo "Refusing to reuse an existing network: ${SMOKE_NETWORK}" >&2
  exit 1
fi
if docker volume inspect "$SMOKE_VOLUME" >/dev/null 2>&1; then
  echo "Refusing to reuse an existing volume: ${SMOKE_VOLUME}" >&2
  exit 1
fi
if docker image inspect "$SMOKE_BACKEND_IMAGE" >/dev/null 2>&1; then
  echo "Refusing to overwrite an existing image: ${SMOKE_BACKEND_IMAGE}" >&2
  exit 1
fi
if docker image inspect "$SMOKE_FRONTEND_IMAGE" >/dev/null 2>&1; then
  echo "Refusing to overwrite an existing image: ${SMOKE_FRONTEND_IMAGE}" >&2
  exit 1
fi
SMOKE_TMP="$(mktemp -d)"
SMOKE_CLEANED=0

export COMPOSE_PROJECT_NAME="$SMOKE_PROJECT"
export UAI_FORGE_BIND_ADDRESS="127.0.0.1"
export UAI_FORGE_API_PORT="$SMOKE_API_PORT"
export UAI_FORGE_WEB_PORT="$SMOKE_WEB_PORT"
export UAI_FORGE_DATA_VOLUME="$SMOKE_VOLUME"
export UAI_FORGE_BACKEND_IMAGE="$SMOKE_BACKEND_IMAGE"
export UAI_FORGE_FRONTEND_IMAGE="$SMOKE_FRONTEND_IMAGE"
export UAI_FORGE_ALLOWED_ORIGINS="http://localhost:${SMOKE_WEB_PORT},http://127.0.0.1:${SMOKE_WEB_PORT}"
export UAI_FORGE_CONTROL_API_KEY=""

cleanup() {
  local exit_code=$?
  trap - EXIT
  if [[ "$exit_code" -ne 0 ]]; then
    docker compose logs --no-color --tail 160 backend frontend >&2 || true
  fi
  if [[ "$SMOKE_CLEANED" -eq 0 ]]; then
    docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
  docker image rm "$SMOKE_BACKEND_IMAGE" "$SMOKE_FRONTEND_IMAGE" >/dev/null 2>&1 || true
  rm -rf "$SMOKE_TMP"
  exit "$exit_code"
}
trap cleanup EXIT

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempt
  for attempt in $(seq 1 120); do
    if curl --fail --silent --output /dev/null "$url" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for ${label}: ${url}" >&2
  return 1
}

wait_for_service_health() {
  local service="$1"
  local container_id=""
  local health_status=""
  local attempt
  for attempt in $(seq 1 120); do
    container_id="$(docker compose ps --quiet "$service")"
    if [[ -n "$container_id" ]]; then
      health_status="$(
        docker inspect \
          --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' \
          "$container_id"
      )"
      if [[ "$health_status" == "healthy" ]]; then
        return 0
      fi
      if [[ "$health_status" == "unhealthy" ]]; then
        echo "Container health check failed for ${service}" >&2
        return 1
      fi
    fi
    sleep 1
  done
  echo "Timed out waiting for Docker health status: ${service} (${health_status:-missing})" >&2
  return 1
}

cd "$SMOKE_ROOT"

docker compose config --quiet
docker compose up --build --detach

wait_for_service_health "backend"
wait_for_service_health "frontend"
wait_for_http "http://127.0.0.1:${SMOKE_API_PORT}/health" "backend health"
wait_for_http "http://127.0.0.1:${SMOKE_WEB_PORT}/" "frontend health"

docker compose exec -T frontend sh -c \
  'test ! -e node_modules/eslint && test ! -e node_modules/drizzle-kit'

docker compose exec -T backend uai-forge doctor >"$SMOKE_TMP/doctor.json"
python3 - "$SMOKE_TMP/doctor.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    doctor = json.load(source)
if doctor.get("status") != "ok":
    raise SystemExit(f"doctor failed: {doctor}")
if doctor.get("agents") != 0 or doctor.get("plugins", 0) < 1:
    raise SystemExit(f"doctor reported unexpected fresh database state: {doctor}")
if doctor.get("providers") != ["anthropic_messages", "openai_compatible"]:
    raise SystemExit(f"doctor reported unexpected provider registry: {doctor}")
if doctor.get("plugin_errors"):
    raise SystemExit(f"doctor reported plugin errors: {doctor['plugin_errors']}")
PY

curl --fail --silent --show-error \
  "http://127.0.0.1:${SMOKE_API_PORT}/api/v1/plugins?kind=provider" \
  >"$SMOKE_TMP/providers.json"
curl --fail --silent --show-error \
  "http://127.0.0.1:${SMOKE_API_PORT}/api/v1/agents" \
  >"$SMOKE_TMP/agents.json"
curl --fail --silent --show-error \
  "http://127.0.0.1:${SMOKE_API_PORT}/api/v1/instances" \
  >"$SMOKE_TMP/instances.json"
curl --fail --silent --show-error \
  "http://127.0.0.1:${SMOKE_API_PORT}/api/v1/model-configs" \
  >"$SMOKE_TMP/model-configs.json"
curl --fail --silent --show-error \
  "http://127.0.0.1:${SMOKE_API_PORT}/api/v1/model-catalog" \
  >"$SMOKE_TMP/model-catalog.json"
curl --fail --silent --show-error \
  "http://127.0.0.1:${SMOKE_API_PORT}/api/v1/runtime-config" \
  >"$SMOKE_TMP/runtime-config.json"

python3 - "$SMOKE_TMP/doctor.json" "$SMOKE_TMP/providers.json" \
  "$SMOKE_TMP/agents.json" "$SMOKE_TMP/instances.json" \
  "$SMOKE_TMP/model-configs.json" "$SMOKE_TMP/model-catalog.json" \
  "$SMOKE_TMP/runtime-config.json" >"$SMOKE_TMP/summary.json" <<'PY'
import json
import sys

records = []
for path in sys.argv[1:]:
    with open(path, encoding="utf-8") as source:
        records.append(json.load(source))
doctor, providers, agents, instances, model_configs, model_catalog, runtime_config = records

provider_ids = [item.get("id") for item in providers]
if provider_ids != ["anthropic_messages", "openai_compatible"]:
    raise SystemExit(f"unexpected provider catalog: {providers}")
catalog_provider_ids = [item.get("id") for item in model_catalog.get("providers", [])]
if catalog_provider_ids != provider_ids:
    raise SystemExit(f"model catalog is out of sync: {model_catalog}")
if not all(item.get("models") for item in model_catalog.get("providers", [])):
    raise SystemExit(f"provider catalog has no recommended models: {model_catalog}")
for label, value in {
    "agents": agents,
    "instances": instances,
    "model_configs": model_configs,
    "runtime_config": runtime_config,
}.items():
    if value != []:
        raise SystemExit(f"fresh database contains {label}: {value}")

print(
    json.dumps(
        {
            "status": "passed",
            "database_state": "empty and database-backed",
            "provider_ids": provider_ids,
            "model_catalog": {
                "providers": catalog_provider_ids,
                "non_empty": True,
            },
            "frontend_dependencies": {
                "development_tools_pruned": True,
                "production_audit": "passed during image build",
            },
            "doctor": {
                "status": doctor["status"],
                "agents": doctor["agents"],
                "plugins": doctor["plugins"],
                "providers": doctor["providers"],
                "plugin_errors": doctor["plugin_errors"],
            },
        },
        ensure_ascii=False,
        indent=2,
    )
)
PY

docker compose down --volumes --remove-orphans
SMOKE_CLEANED=1
docker image rm "$SMOKE_BACKEND_IMAGE" "$SMOKE_FRONTEND_IMAGE" >/dev/null

if [[ -n "$(docker compose ps --quiet)" ]]; then
  echo "Smoke containers remain after cleanup" >&2
  exit 1
fi
if docker volume inspect "$SMOKE_VOLUME" >/dev/null 2>&1; then
  echo "Smoke volume remains after cleanup: ${SMOKE_VOLUME}" >&2
  exit 1
fi
if docker network inspect "$SMOKE_NETWORK" >/dev/null 2>&1; then
  echo "Smoke network remains after cleanup: ${SMOKE_NETWORK}" >&2
  exit 1
fi
if docker image inspect "$SMOKE_BACKEND_IMAGE" >/dev/null 2>&1; then
  echo "Smoke backend image remains after cleanup: ${SMOKE_BACKEND_IMAGE}" >&2
  exit 1
fi
if docker image inspect "$SMOKE_FRONTEND_IMAGE" >/dev/null 2>&1; then
  echo "Smoke frontend image remains after cleanup: ${SMOKE_FRONTEND_IMAGE}" >&2
  exit 1
fi

cat "$SMOKE_TMP/summary.json"

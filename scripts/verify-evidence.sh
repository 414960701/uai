#!/usr/bin/env bash
set -u -o pipefail

VERIFY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERIFY_OUTPUT="${UAI_FORGE_EVIDENCE_OUTPUT:-${VERIFY_ROOT}/artifacts/evidence-summary.json}"
VERIFY_TMP="$(mktemp -d)"
VERIFY_STATUS_FILE="${VERIFY_TMP}/statuses.tsv"
VERIFY_FAILURES=0

cleanup() {
  rm -rf "${VERIFY_TMP}"
}
trap cleanup EXIT

run_step() {
  local name="$1"
  shift
  echo "== ${name} =="
  set +e
  "$@"
  local exit_code=$?
  set -e
  printf '%s\t%s\t%s\n' "${name}" "${exit_code}" "$*" >>"${VERIFY_STATUS_FILE}"
  if [[ "${exit_code}" -ne 0 ]]; then
    VERIFY_FAILURES=$((VERIFY_FAILURES + 1))
  fi
}

cd "${VERIFY_ROOT}"
VERIFY_PYTHON="${VENV_PYTHON:-${VERIFY_ROOT}/.venv/bin/python}"
if [[ ! -x "${VERIFY_PYTHON}" ]]; then
  VERIFY_PYTHON="${PYTHON:-python3}"
fi

run_step "backend_tests" "${VERIFY_PYTHON}" -m pytest backend/tests -q
run_step "frontend_lint" npm run lint
run_step "frontend_typecheck" npm run typecheck
run_step "frontend_tests" npm test
run_step "compose_config" docker compose config --quiet
run_step "git_diff_check" git diff --check

mkdir -p "$(dirname "${VERIFY_OUTPUT}")"
python3 - "${VERIFY_OUTPUT}" "${VERIFY_STATUS_FILE}" "${VERIFY_FAILURES}" "${VERIFY_PYTHON}" <<'PY'
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

output_path = Path(sys.argv[1])
status_path = Path(sys.argv[2])
failure_count = int(sys.argv[3])
python_executable = sys.argv[4]

commands = []
for line in status_path.read_text(encoding="utf-8").splitlines():
    name, exit_code, command = line.split("\t", 2)
    commands.append(
        {
            "name": name,
            "command": command,
            "exit_code": int(exit_code),
            "status": "passed" if int(exit_code) == 0 else "failed",
        }
    )

def version(command):
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip() or None
    except OSError:
        return None

try:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip() or None
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.strip() or None
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
except OSError:
    commit = branch = None
    dirty = None

payload = {
    "schema_version": "uai-forge.evidence-summary/1.0",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "status": "passed" if failure_count == 0 else "failed",
    "failure_count": failure_count,
    "repository": {"branch": branch, "commit": commit, "dirty": dirty},
    "runtimes": {
        "python": version([python_executable, "--version"]),
        "node": version(["node", "--version"]),
        "npm": version(["npm", "--version"]),
    },
    "commands": commands,
    "secret_policy": {
        "command_output_embedded": False,
        "plaintext_credentials_embedded": False,
    },
}
output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"evidence summary: {output_path}")
PY

if [[ "${VERIFY_FAILURES}" -ne 0 ]]; then
  exit 1
fi

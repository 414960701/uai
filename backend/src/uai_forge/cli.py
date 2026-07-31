"""Command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import json

import uvicorn

from .api import create_app
from .container import Container
from .models import PluginKind
from .settings import Settings


async def _doctor(settings: Settings) -> int:
    container = Container.build(settings)
    # Doctor is deliberately read-only.  Runtime startup performs migrations,
    # but diagnostics must not create a new database, stamp schema_meta, or
    # partially migrate a failed database while the operator is inspecting it.
    schema = await container.repository.compatibility_status()
    if schema.get("status") != "compatible":
        is_new = schema.get("status") == "new"
        payload = {
            "database": settings.database_path,
            "status": "ok" if is_new else "migration_required" if schema.get("status") == "migratable" else "incompatible",
            "agents": 0,
            "plugins": len(container.registry.manifests()),
            "providers": [
                manifest.id
                for manifest in container.registry.manifests(PluginKind.PROVIDER)
            ],
            "plugin_errors": container.registry.discovery_errors,
            "schema": schema,
            "migration": {
                "dry_run": True,
                "writes_performed": False,
                "pending": ["v1_to_v2"] if schema.get("status") == "migratable" else [],
            },
        }
        if not is_new and schema.get("status") != "migratable":
            payload["remediation"] = schema.get(
                "remediation",
                {"action": "backup_and_rebuild", "target": "database"},
            )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if is_new else 2

    agents = await container.repository.list_agents("default")
    payload = {
        "database": settings.database_path,
        "agents": len(agents),
        "plugins": len(container.registry.manifests()),
        "providers": [
            manifest.id
            for manifest in container.registry.manifests(PluginKind.PROVIDER)
        ],
        "plugin_errors": container.registry.discovery_errors,
        "schema": schema,
        "migration": {"dry_run": True, "writes_performed": False, "pending": []},
        "status": "ok" if not container.registry.discovery_errors else "degraded",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="uai-forge")
    subparsers = parser.add_subparsers(dest="command")
    serve = subparsers.add_parser("serve", help="Start the FastAPI control plane")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    subparsers.add_parser("doctor", help="Validate storage and plugin discovery")
    args = parser.parse_args()
    settings = Settings()
    if args.command in (None, "serve"):
        uvicorn.run(
            create_app(settings),
            host=args.host or settings.host,
            port=args.port or settings.port,
        )
        return
    if args.command == "doctor":
        raise SystemExit(asyncio.run(_doctor(settings)))


if __name__ == "__main__":
    main()

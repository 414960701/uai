"""Environment-backed service settings without hidden global configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Settings:
    database_path: str = field(
        default_factory=lambda: os.environ.get(
            "UAI_FORGE_DATABASE_PATH",
            str(Path(".uai-forge/forge.db").resolve()),
        )
    )
    control_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("UAI_FORGE_CONTROL_API_KEY")
    )
    # Bootstrap-only secret-manager reference used to encrypt/decrypt
    # database-backed provider credentials.  It is never persisted in SQLite
    # or returned by the control API.
    credential_master_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("UAI_FORGE_CREDENTIAL_MASTER_KEY")
    )
    allowed_origins: List[str] = field(
        default_factory=lambda: [
            item.strip()
            for item in os.environ.get(
                "UAI_FORGE_ALLOWED_ORIGINS",
                "http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if item.strip()
        ]
    )
    host: str = field(default_factory=lambda: os.environ.get("UAI_FORGE_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.environ.get("UAI_FORGE_PORT", "8000")))

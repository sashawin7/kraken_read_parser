"""Run metadata helpers."""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any, Mapping

from . import __version__
from .schemas import RUN_METADATA_SCHEMA


def base_metadata() -> dict[str, Any]:
    return {
        "package_version": __version__,
        "python_version": sys.version,
        "platform": platform.platform(),
    }


def file_identity(path: Path) -> dict[str, Any]:
    identity: dict[str, Any] = {"path": str(path)}
    try:
        stat = path.stat()
    except OSError as exc:
        identity["exists"] = False
        identity["error"] = str(exc)
        return identity
    identity.update({
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    })
    return identity


def run_metadata_schema() -> dict[str, Any]:
    return dict(RUN_METADATA_SCHEMA)


def write_metadata(path: Path, metadata: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")

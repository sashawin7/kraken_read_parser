"""Run metadata helpers."""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path
from typing import Any, Mapping

from . import __version__


def base_metadata() -> dict[str, Any]:
    return {
        "package_version": __version__,
        "python_version": sys.version,
        "platform": platform.platform(),
    }


def write_metadata(path: Path, metadata: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")

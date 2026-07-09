"""Validation helpers for CLI inputs and outputs."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Iterable


def require_existing_path(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")


def ensure_outdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def protect_outputs(paths: Iterable[Path], *, overwrite: bool) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing and not overwrite:
        raise FileExistsError("Output file(s) already exist; use --overwrite to replace: " + ", ".join(existing))


def require_executable(executable: str) -> None:
    executable_path = Path(executable)
    if executable_path.exists() and os.access(executable_path, os.X_OK):
        return
    if shutil.which(executable) is None:
        raise FileNotFoundError(f"Kraken2 executable not found or not executable on PATH: {executable}")

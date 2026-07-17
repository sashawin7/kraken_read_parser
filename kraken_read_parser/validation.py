"""Validation helpers for safe Kraken2 runs."""
from __future__ import annotations
import os, re, shutil, tempfile
from pathlib import Path
from typing import Iterable

_SAMPLE=re.compile(r'^[A-Za-z0-9._-]+$')
def validate_sample_id(value:str)->str:
    if value in {'','.', '..'} or not _SAMPLE.fullmatch(value): raise ValueError("sample ID must match ^[A-Za-z0-9._-]+$ and cannot be . or ..")
    return value
def validate_positive_integer(value:int,label:str)->int:
    if value < 1: raise ValueError(f"{label} must be at least 1")
    return value
def require_existing_path(path:Path,label:str)->None:
    if not path.exists(): raise FileNotFoundError(f"{label} does not exist: {path}")
def require_regular_nonempty_file(path:Path,label:str)->None:
    require_existing_path(path,label)
    if not path.is_file(): raise ValueError(f"{label} must be a regular file: {path}")
    if path.stat().st_size == 0: raise ValueError(f"{label} is empty: {path}")
    if not os.access(path,os.R_OK): raise PermissionError(f"{label} is not readable: {path}")
def require_directory(path:Path,label:str)->None:
    require_existing_path(path,label)
    if not path.is_dir(): raise ValueError(f"{label} must be a directory: {path}")
    if not os.access(path,os.R_OK|os.X_OK): raise PermissionError(f"{label} is not readable/traversable: {path}")
def ensure_outdir(path:Path)->None:
    path.mkdir(parents=True,exist_ok=True)
    if not path.is_dir(): raise ValueError(f"output directory is not a directory: {path}")
    try:
      fd,name=tempfile.mkstemp(prefix='.kraken-read-parser-',dir=path); os.close(fd); Path(name).unlink()
    except OSError as exc: raise PermissionError(f"output directory is not writable: {path}: {exc}") from exc
def protect_outputs(paths:Iterable[Path],*,overwrite:bool)->None:
    existing=[str(p) for p in paths if p.exists()]
    if existing and not overwrite: raise FileExistsError('Output file(s) already exist; use --overwrite to replace: '+', '.join(existing))
def require_executable(executable:str)->None:
    p=Path(executable)
    if (p.exists() and os.access(p,os.X_OK)) or shutil.which(executable): return
    raise FileNotFoundError(f"executable not found or not executable on PATH: {executable}")

"""Kraken2 command construction, execution, and output checks."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .metadata import base_metadata, file_identity, run_metadata_schema, write_metadata
from .parser import parse_kraken2_file
from .validation import protect_outputs, require_executable, require_existing_path


@dataclass(frozen=True)
class KrakenOutputs:
    output_tsv: Path
    report_tsv: Path
    stderr_log: Path
    metadata_json: Path


def planned_outputs(outdir: Path, sample_id: str) -> KrakenOutputs:
    return KrakenOutputs(
        output_tsv=outdir / f"{sample_id}.kraken2.tsv",
        report_tsv=outdir / f"{sample_id}.kraken2.report.tsv",
        stderr_log=outdir / f"{sample_id}.kraken2.stderr.log",
        metadata_json=outdir / f"{sample_id}.run_metadata.json",
    )


def build_kraken2_command(
    *,
    kraken2_bin: str,
    db: Path,
    threads: int,
    outputs: KrakenOutputs,
    r1: Path,
    r2: Path,
    memory_mapping: bool = False,
) -> list[str]:
    command = [
        kraken2_bin,
        "--paired",
        "--db",
        str(db),
        "--threads",
        str(threads),
        "--output",
        str(outputs.output_tsv),
        "--report",
        str(outputs.report_tsv),
    ]
    if memory_mapping:
        command.append("--memory-mapping")
    command.extend([str(r1), str(r2)])
    return command


def sanity_check_output(path: Path, *, rows: int = 1000, require_paired: bool = True) -> tuple[int, int]:
    checked = 0
    paired = 0
    for record in parse_kraken2_file(path, strict=True):
        checked += 1
        if record.has_mate_separator:
            paired += 1
        if checked >= rows:
            break
    if checked == 0:
        raise ValueError(f"Kraken2 output is empty: {path}")
    if require_paired and paired < checked:
        raise ValueError(
            f"Kraken2 output does not look like paired output: {paired}/{checked} checked rows contain '|:|' in hitlist field. "
            "Stage 2 expects paired Kraken2 evidence."
        )
    return checked, paired


def run_kraken2(
    *,
    r1: Path,
    r2: Path,
    db: Path,
    sample_id: str,
    outdir: Path,
    threads: int,
    kraken2_bin: str = "kraken2",
    overwrite: bool = False,
    check_output_lines: int = 1000,
    dry_run: bool = False,
    memory_mapping: bool = False,
) -> dict:
    r1 = r1.resolve(); r2 = r2.resolve(); db = db.resolve(); outdir = outdir.resolve()
    require_existing_path(r1, "R1 FASTQ")
    require_existing_path(r2, "R2 FASTQ")
    require_existing_path(db, "Kraken2 database")
    outdir.mkdir(parents=True, exist_ok=True)
    outputs = planned_outputs(outdir, sample_id)
    protect_outputs(outputs.__dict__.values(), overwrite=overwrite)
    require_executable(kraken2_bin)
    command = build_kraken2_command(
        kraken2_bin=kraken2_bin,
        db=db,
        threads=threads,
        outputs=outputs,
        r1=r1,
        r2=r2,
        memory_mapping=memory_mapping,
    )
    start = datetime.now(timezone.utc)
    metadata = base_metadata() | run_metadata_schema() | {
        "sample_id": sample_id,
        "r1": str(r1), "r2": str(r2), "kraken2_db": str(db), "outdir": str(outdir),
        "inputs": {"r1": file_identity(r1), "r2": file_identity(r2), "kraken2_db": file_identity(db)},
        "threads": threads, "memory_mapping": memory_mapping, "kraken2_executable": kraken2_bin, "command": command,
        "start_time": start.isoformat(), "output_files": {k: str(v) for k, v in outputs.__dict__.items()},
    }
    if dry_run:
        metadata |= {"dry_run": True, "end_time": start.isoformat(), "elapsed_seconds": 0.0, "exit_code": None}
        return metadata
    t0 = time.monotonic()
    with outputs.stderr_log.open("w", encoding="utf-8") as stderr_handle:
        proc = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=stderr_handle, text=True)
    end = datetime.now(timezone.utc)
    metadata |= {"dry_run": False, "end_time": end.isoformat(), "elapsed_seconds": time.monotonic() - t0, "exit_code": proc.returncode}
    write_metadata(outputs.metadata_json, metadata)
    if proc.returncode != 0:
        raise RuntimeError(f"Kraken2 failed with exit code {proc.returncode}; see {outputs.stderr_log}")
    for path, label in [(outputs.output_tsv, "Kraken2 output"), (outputs.report_tsv, "Kraken2 report")]:
        if not path.exists():
            raise FileNotFoundError(f"Expected {label} file is missing: {path}")
        if path.stat().st_size == 0:
            raise ValueError(f"Expected {label} file is empty: {path}")
    sanity_check_output(outputs.output_tsv, rows=check_output_lines)
    return metadata

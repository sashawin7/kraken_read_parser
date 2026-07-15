"""Streaming paired FASTQ validation and conservative read-name normalization."""
from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from .metadata import base_metadata, file_identity
from .schemas import FASTQ_VALIDATION_SCHEMA
from .validation import protect_outputs


class FastqValidationError(ValueError):
    """Raised when paired FASTQ validation fails with an actionable message."""


@dataclass(frozen=True)
class FastqRecord:
    header: str
    sequence: str
    separator: str
    quality: str
    record_number: int

    @property
    def original_id(self) -> str:
        return self.header[1:].strip()


def normalize_read_name(header_or_id: str) -> str:
    """Return a conservative template id for mate comparison.

    Only two common mate annotations are interpreted: a terminal ``/1`` or
    ``/2`` on the first whitespace-delimited token, and an Illumina-style mate
    field where the second whitespace-delimited token starts with ``1:`` or
    ``2:``. Other identifiers are preserved exactly apart from the leading ``@``
    and surrounding newline/outer whitespace.
    """
    text = header_or_id.strip()
    if text.startswith("@"):
        text = text[1:]
    parts = text.split()
    if not parts:
        return ""
    token = parts[0]
    if len(token) > 2 and token[-2:] in {"/1", "/2"}:
        return token[:-2]
    # For Illumina headers, the first token is already the template id; the
    # second token (1:N:0:... or 2:N:0:...) encodes the mate and is ignored.
    if len(parts) > 1 and (parts[1].startswith("1:") or parts[1].startswith("2:")):
        return token
    return text


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("rt", encoding="utf-8", newline="")


def _read_record(handle: TextIO, *, path: Path, record_number: int) -> FastqRecord | None:
    lines: list[str] = []
    for _ in range(4):
        line = handle.readline()
        if line == "":
            break
        lines.append(line.rstrip("\n\r"))
    if not lines:
        return None
    if len(lines) != 4:
        raise FastqValidationError(f"{path}: record {record_number} is incomplete; expected 4 FASTQ lines, found {len(lines)}")
    rec = FastqRecord(*lines, record_number=record_number)
    if not rec.header.startswith("@") or len(rec.header) == 1:
        raise FastqValidationError(f"{path}: record {record_number} has invalid FASTQ header; expected non-empty line starting with '@'")
    if not rec.separator.startswith("+"):
        raise FastqValidationError(f"{path}: record {record_number} has invalid FASTQ separator; expected line starting with '+'")
    if len(rec.sequence) != len(rec.quality):
        raise FastqValidationError(
            f"{path}: record {record_number} sequence length ({len(rec.sequence)}) does not match quality length ({len(rec.quality)})"
        )
    return rec


def validate_paired_fastq(*, r1: Path, r2: Path, sample_id: str, outdir: Path, overwrite: bool = False) -> dict:
    r1 = r1.resolve(); r2 = r2.resolve(); outdir = outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    output = outdir / f"{sample_id}.fastq_validation.json"
    protect_outputs([output], overwrite=overwrite)
    start = datetime.now(timezone.utc)
    result = base_metadata() | FASTQ_VALIDATION_SCHEMA | {
        "sample_id": sample_id,
        "validation_status": "failed",
        "start_time": start.isoformat(),
        "end_time": None,
        "inputs": {"r1": file_identity(r1), "r2": file_identity(r2)},
        "output_file": str(output),
        "files": {
            "r1": {"path": str(r1), "records": 0, "sequence_bases": 0},
            "r2": {"path": str(r2), "records": 0, "sequence_bases": 0},
        },
        "pairs": {"records": 0},
        "read_name_normalization": {
            "strategy": "conservative_mate_suffix_only",
            "removes": ["terminal /1 or /2 on first identifier token", "Illumina mate field after whitespace when it starts with 1: or 2:"],
            "preserves": "all other identifier text for comparison",
            "duplicate_detection": "not performed; exact whole-file duplicate detection is intentionally omitted to keep validation bounded-memory",
        },
        "errors": [],
    }
    try:
        with _open_text(r1) as h1, _open_text(r2) as h2:
            n = 1
            while True:
                rec1 = _read_record(h1, path=r1, record_number=n)
                rec2 = _read_record(h2, path=r2, record_number=n)
                if rec1 is None and rec2 is None:
                    break
                if rec1 is None or rec2 is None:
                    side = "R1" if rec1 is None else "R2"
                    raise FastqValidationError(f"paired FASTQ count mismatch at pair {n}: {side} ended before its mate file")
                id1 = normalize_read_name(rec1.header)
                id2 = normalize_read_name(rec2.header)
                if id1 != id2:
                    raise FastqValidationError(
                        f"pair {n} read identifiers do not match after conservative normalization: R1='{rec1.original_id}' -> '{id1}', R2='{rec2.original_id}' -> '{id2}'"
                    )
                result["files"]["r1"]["records"] += 1
                result["files"]["r2"]["records"] += 1
                result["files"]["r1"]["sequence_bases"] += len(rec1.sequence)
                result["files"]["r2"]["sequence_bases"] += len(rec2.sequence)
                result["pairs"]["records"] += 1
                n += 1
        if result["pairs"]["records"] == 0:
            raise FastqValidationError("paired FASTQ inputs are empty; no records found")
        result["validation_status"] = "passed"
    except (OSError, EOFError, gzip.BadGzipFile, UnicodeDecodeError) as exc:
        result["errors"].append({"message": f"failed to read FASTQ input: {exc}"})
    except FastqValidationError as exc:
        result["errors"].append({"message": str(exc)})
    result["end_time"] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["validation_status"] != "passed":
        raise FastqValidationError(f"FASTQ validation failed; see {output}: {result['errors'][0]['message']}")
    return result

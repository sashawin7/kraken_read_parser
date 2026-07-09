"""Streaming parser for Kraken2 paired-output records."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Optional, TextIO, Union


@dataclass(frozen=True)
class KrakenRecord:
    """One Kraken2 output row with paired-read convenience fields."""

    status: str
    read_id: str
    taxid: str
    length_raw: str
    length_r1: Optional[int]
    length_r2: Optional[int]
    hitlist_raw: str
    hitlist_r1: str
    hitlist_r2: Optional[str]

    @property
    def has_mate_separator(self) -> bool:
        return "|:|" in self.hitlist_raw


class KrakenParserError(ValueError):
    """Raised when a Kraken2 row cannot be parsed in strict mode."""


def _parse_length(length_raw: str) -> tuple[Optional[int], Optional[int]]:
    parts = length_raw.split("|")
    try:
        if len(parts) == 1:
            return int(parts[0]), None
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None
    return None, None


def parse_line(line: str, *, strict: bool = True, line_number: Optional[int] = None) -> Optional[KrakenRecord]:
    """Parse one Kraken2 TSV line.

    Malformed rows raise :class:`KrakenParserError` in strict mode and return
    ``None`` otherwise.
    """
    row = line.rstrip("\n")
    fields = row.split("\t")
    if len(fields) != 5:
        location = f" on line {line_number}" if line_number is not None else ""
        message = f"Malformed Kraken2 row{location}: expected 5 tab-delimited fields, found {len(fields)}"
        if strict:
            raise KrakenParserError(message)
        return None
    status, read_id, taxid, length_raw, hitlist_raw = fields
    length_r1, length_r2 = _parse_length(length_raw)
    if "|:|" in hitlist_raw:
        hitlist_r1, hitlist_r2 = hitlist_raw.split("|:|", 1)
    else:
        hitlist_r1, hitlist_r2 = hitlist_raw, None
    return KrakenRecord(status, read_id, taxid, length_raw, length_r1, length_r2, hitlist_raw, hitlist_r1, hitlist_r2)


def parse_kraken2(handle: Iterable[str], *, strict: bool = True) -> Iterator[KrakenRecord]:
    """Stream Kraken2 records from an iterable of lines."""
    for line_number, line in enumerate(handle, start=1):
        if not line.strip():
            continue
        record = parse_line(line, strict=strict, line_number=line_number)
        if record is not None:
            yield record


def parse_kraken2_file(path: Union[str, Path], *, strict: bool = True) -> Iterator[KrakenRecord]:
    """Stream Kraken2 records from a path."""
    with Path(path).open("r", encoding="utf-8") as handle:
        yield from parse_kraken2(handle, strict=strict)

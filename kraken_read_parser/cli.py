"""Command-line interface."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .fastq import FastqValidationError, validate_paired_fastq
from .kraken import planned_outputs, run_kraken2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kraken-read-parser")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run-kraken", help="Run Kraken2 on paired FASTQ files and save Stage 1 artifacts")
    run.add_argument("--r1", required=True, type=Path)
    run.add_argument("--r2", required=True, type=Path)
    run.add_argument("--db", required=True, type=Path)
    run.add_argument("--sample-id", required=True)
    run.add_argument("--outdir", required=True, type=Path)
    run.add_argument("--threads", required=True, type=int)
    run.add_argument("--kraken2-bin", default="kraken2")
    run.add_argument("--overwrite", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--check-output-lines", type=int, default=1000)
    validate = sub.add_parser("validate-fastq", help="Validate paired FASTQ integrity without running Kraken2")
    validate.add_argument("--r1", required=True, type=Path)
    validate.add_argument("--r2", required=True, type=Path)
    validate.add_argument("--sample-id", required=True)
    validate.add_argument("--outdir", required=True, type=Path)
    validate.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run-kraken":
        try:
            metadata = run_kraken2(
                r1=args.r1, r2=args.r2, db=args.db, sample_id=args.sample_id, outdir=args.outdir,
                threads=args.threads, kraken2_bin=args.kraken2_bin, overwrite=args.overwrite,
                dry_run=args.dry_run, check_output_lines=args.check_output_lines,
            )
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if args.dry_run:
            outputs = planned_outputs(args.outdir.resolve(), args.sample_id)
            print("Kraken2 command:")
            print(" ".join(metadata["command"]))
            print("Planned output files:")
            for path in outputs.__dict__.values():
                print(path)
        else:
            print(json.dumps(metadata["output_files"], indent=2, sort_keys=True))
    if args.command == "validate-fastq":
        try:
            result = validate_paired_fastq(r1=args.r1, r2=args.r2, sample_id=args.sample_id, outdir=args.outdir, overwrite=args.overwrite)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(json.dumps({"validation_status": result["validation_status"], "output_file": result["output_file"], "pairs": result["pairs"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

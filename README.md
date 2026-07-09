# kraken_read_parser

`kraken_read_parser` is a Python-first Stage 1 repository for paired-end FASTQ filtering workflows that begin with Kraken2 evidence.

The intended input domain is paired-end **human genomic DNA sequencing read products** such as WGS/WES-style FASTQ data, where most read pairs are expected to be human and a minority may contain nonhuman, contaminant, uncertain, or discordant Kraken2 evidence. This project is **not** designed around RNA-seq, metatranscriptomics, amplicon sequencing, or primarily microbial/metagenomic input.

## Stage 1 scope

Stage 1 only:

- runs Kraken2 in paired-end mode;
- saves reproducible Kraken2 output, report, stderr, and metadata artifacts;
- provides a streaming parser seam for Kraken2 paired-output records.

Stage 1 does **not** compute final human/nonhuman scores, write human/nonhuman FASTQ bins, parse FASTQ sequence content, query Kraken2 databases directly, or hard-code taxonomy thresholds.

Future Stage 2 work will use the preserved numeric Kraken2 output to compute per-read-pair metrics and split paired FASTQs into `human`, `nonhuman`, `uncertain`, and `discordant_confident` bins.

## Installation for development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
```

## Command-line usage

```bash
kraken-read-parser run-kraken \
  --r1 normal_R1.fastq.gz \
  --r2 normal_R2.fastq.gz \
  --db /path/to/kraken2_db \
  --sample-id normal_example \
  --outdir results \
  --threads 8
```

Optional flags include:

- `--kraken2-bin`: executable path/name, default `kraken2`;
- `--overwrite`: permit replacement of existing output artifacts;
- `--dry-run`: print the command and planned files without running Kraken2;
- `--check-output-lines`: number of Kraken2 rows to sanity-check after execution, default `1000`.

The Kraken2 command constructed is equivalent to:

```bash
kraken2 --paired --db DB --threads THREADS \
  --output OUTDIR/SAMPLE_ID.kraken2.tsv \
  --report OUTDIR/SAMPLE_ID.kraken2.report.tsv \
  R1 R2
```

Stage 1 intentionally does not pass `--classified-out`, `--unclassified-out`, `--use-names`, `--quick`, or `--confidence`.

## Expected outputs

Each non-dry run writes:

- `OUTDIR/SAMPLE_ID.kraken2.tsv`
- `OUTDIR/SAMPLE_ID.kraken2.report.tsv`
- `OUTDIR/SAMPLE_ID.kraken2.stderr.log`
- `OUTDIR/SAMPLE_ID.run_metadata.json`

Metadata records the sample id, absolute input paths, database path, output directory, thread count, Kraken2 executable, full argv list, start/end times, elapsed seconds, exit code, output file paths, package version, Python version, and platform string.

## Parser behavior

The parser streams Kraken2 output as tab-delimited five-field records:

1. status
2. read id
3. taxid
4. length
5. raw hitlist

For paired reads, mate lengths may be separated with `|`, and mate hitlists are expected to be separated with `|:|`. Parsed `KrakenRecord` objects retain raw fields and expose split mate fields. The parser does not classify reads or compute human/nonhuman metrics.

## Included example FASTQ files

This repository currently includes:

- `normal_R1.fastq.gz` and `normal_R2.fastq.gz`: human-ish compressed paired FASTQ example files. Treat these as the representative example for the intended human genomic sequencing command-line workflow.
- `mutant_R1.fastq` and `mutant_R2.fastq`: uncompressed toy/control paired FASTQ example files with read ids such as `mutant-no_snps.gff-*`. Treat these only as optional plumbing/control examples, not as representative of the intended human genomic input domain.

These files are development/example inputs only. They are not a training set, not a benchmark dataset, and not evidence for final scoring thresholds. Do not infer final classification behavior from names such as `normal` or `mutant`.

## Testing

Ordinary unit tests mock Kraken2 execution and do not require a real Kraken2 database. Real command-line runs require both Kraken2 and an existing Kraken2 database directory.

```bash
pytest
```

## Limitations and next steps

- No final human/nonhuman scoring is implemented.
- No FASTQ binning output is implemented.
- No taxonomy-specific human/nonhuman logic is hard-coded.
- Optional integration tests against a real Kraken2 database can be added later behind an explicit database path.

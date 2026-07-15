# Machine-readable schemas

All JSON or tabular artifacts produced by Stage 2 commands carry an explicit `schema_name` and integer `schema_version`. Breaking changes require a new integer version; compatible additive fields may stay within the same version when documented and tested.

Declared schemas in this PR are:

| Artifact | Schema name | Version | Status |
| --- | --- | ---: | --- |
| FASTQ validation JSON | `kraken_read_parser.fastq_validation` | 1 | Implemented |
| Kraken2 run metadata JSON | `kraken_read_parser.run_metadata` | 1 | Implemented by extending existing metadata |
| Future read evidence table | `kraken_read_parser.read_evidence` | 1 | Reserved declaration only |
| Future pair evidence table | `kraken_read_parser.pair_evidence` | 1 | Reserved declaration only |
| Future binning manifest JSON | `kraken_read_parser.binning_manifest` | 1 | Reserved declaration only |

## FASTQ validation JSON v1

`validate-fastq` writes `OUTDIR/SAMPLE.fastq_validation.json` with:

- package, Python, and platform context;
- `schema_name` and `schema_version`;
- `sample_id`, start/end timestamps, and output path;
- scalable input file identity: absolute path, existence, size in bytes, and nanosecond mtime;
- per-file record and sequence-base counts;
- paired record count;
- validation status, `passed` or `failed`;
- a list of actionable errors for failed validation;
- a read-name-normalization description, including the explicit duplicate-ID limitation.

Full content hashes are intentionally not computed by default because WGS FASTQs are large and validation already performs a full content scan. Size and mtime provide inexpensive provenance suitable for rerun auditing; stronger hashes can be added later as an opt-in schema extension.

## Run metadata JSON v1

`run-kraken` keeps the Stage 1 filename and fields in `OUTDIR/SAMPLE.run_metadata.json`, and adds schema identity plus reusable input identity for R1, R2, and the Kraken2 database path. The command still records package version, Python/platform information, sample id, inputs, database, output directory, thread count, memory-mapping setting, executable, argv, timestamps, output paths, dry-run state, elapsed seconds, and exit status.

## Reserved future schemas

The read evidence, pair evidence, and binning manifest schema names are declared now so future PRs can refer to stable artifact families. This PR does not implement taxonomy loading, biological labels, policy thresholds, evidence tables, or FASTQ binning.

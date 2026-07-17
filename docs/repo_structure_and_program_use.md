# Repository structure and program-use guide

This is the operational reference for the current `kraken_read_parser` checkout. It is deliberately based on the code and CLI in this repository, not on a proposed Stage 2 design. Substitute all paths and resource settings with verified values for the system where a job will run.

## A. Executive summary

`kraken_read_parser` is currently a **Stage 1 evidence-capture tool** for paired human-genomic FASTQ products. Its implemented workflow is:

```text
paired FASTQ validation
→ Kraken2 execution in paired mode
→ raw Kraken2 output preservation
→ database/report provenance and non-biological report summaries
```

`validate-fastq` streams both FASTQs together and verifies FASTQ structure and mate synchronization. `inspect-db` preflights a Kraken2 database and saves `kraken2-inspect` output. `run-kraken` runs Kraken2, preserves its raw numeric per-read output, checks an initial set of output rows for paired form, parses the report, and writes provenance plus simple accounting/top-taxa summaries.

The reusable evidence artifact is `SAMPLE.kraken2.tsv`. Keeping it means later interpretation policies can be changed without rerunning a costly WGS Kraken2 classification. The report and summaries are useful accounting/provenance views, not biological conclusions.

This repository **does not currently** assign final human/nonhuman labels, load/query taxonomy for biological interpretation, make lineage-aware decisions, extract taxon reads, or write synchronized FASTQ bins. Those are planned Stage 2 capabilities described in `docs/stage2_planning.md`, not commands available now. In particular, a report taxon or raw Kraken result is not itself a safe human/nonhuman filtering decision.

## B. Repository map

| Path | Purpose and main entry points | Important outputs/side effects and connections |
| --- | --- | --- |
| `README.md` | Short project overview, basic examples, safety warning, and Stage 2 context. | Links to this guide, schemas, and the planning document. Source code is authoritative if prose conflicts. |
| `pyproject.toml` | Packaging metadata: package `kraken-read-parser`, version `0.2.0`, Python `>=3.9`, console entry point, and `pytest` development extra. | Installing it exposes `kraken-read-parser = kraken_read_parser.cli:main`. |
| `docs/` | Project documentation. `schemas.md` describes artifact schemas; `stage2_planning.md` is a future-work playbook. | This file is the current operational guide; planning concepts are not implemented unless corroborated by code. |
| `kraken_read_parser/__init__.py` | Defines `__version__`. | Used in metadata provenance. |
| `kraken_read_parser/cli.py` | Public CLI parser and `main()`. | Defines exactly three subcommands: `run-kraken`, `inspect-db`, and `validate-fastq`; catches errors, prints `ERROR: ...`, and exits 1. Treat CLI flags as public behavior. |
| `kraken_read_parser/fastq.py` | Streaming FASTQ validation; `validate_paired_fastq`, `normalize_read_name`, `FastqValidationError`. | Writes validation JSON even for normal validation/read failures. It validates syntax/synchronization, not taxonomy or duplicate IDs. |
| `kraken_read_parser/kraken.py` | Kraken2 command construction/execution; `run_kraken2`, `build_kraken2_command`, `planned_outputs`, `sanity_check_output`. | Writes raw evidence, reports, stderr, metadata, summary, and top-taxa files. Its functions are implementation APIs; use the CLI for operations. |
| `kraken_read_parser/parser.py` | Streaming five-column Kraken output parser; `KrakenRecord`, `parse_kraken2_file`. | Used only for post-run shape checking. It does not score or label reads. |
| `kraken_read_parser/report.py` | Parses six- or eight-column reports and derives six-column compatibility reports. | Used after Kraken2 exits; a parse/accounting error makes metadata `post_run_validation_failed`. Not a biological interpretation module. |
| `kraken_read_parser/database.py` | DB preflight and `kraken2-inspect` wrapper; `validate_kraken_database`, `inspect_database`. | Validates core files, records optional taxonomy availability, preserves inspect output/provenance. It does not parse taxonomy into lineages. |
| `kraken_read_parser/metadata.py` | Metadata identity/atomic-write helpers. | Metadata JSON writes use a temporary file followed by atomic replace. File identity is path/size/mtime/readability, not content hashing. |
| `kraken_read_parser/schemas.py` | Current schema-name/version constants. | Declares FASTQ validation, run metadata, database provenance, and Kraken summary schema families, all v1. |
| `kraken_read_parser/validation.py` | Shared safe-run validation helpers. | Enforces sample IDs and positive values for `run-kraken`, input/db checks, executable lookup, writable output dirs, and overwrite protection. |
| `tests/` | Unit tests for CLI, database checks, FASTQ validation, command behavior, parser, and reports. | Kraken2 subprocesses are mocked; tests do not demonstrate a real database/WGS run. |
| `normal_R1.fastq.gz`, `normal_R2.fastq.gz` | Small compressed example pair. | Development examples only, not real WGS evidence. |
| `mutant_R1.fastq`, `mutant_R2.fastq` | Small uncompressed control/plumbing examples. | Not representative human-genomic input. |
| `.gitignore` | Prevents common generated products and sensitive/bulky bioinformatics files from being added. | It ignores raw Kraken outputs, metadata/validation files, databases, SIFs, work dirs, BAM/CRAM, etc.; check `git status` before every commit. |

No separate workflow/Nextflow module, FASTQ-binning module, or taxon-extraction module exists in this checkout.

## C. Installation and environment assumptions

The package requires Python **3.9 or newer**. Runtime code uses the standard library; `pytest>=7` is the sole declared development extra. Real classifications also require an executable `kraken2` and a readable Kraken2 database. `inspect-db` additionally requires `kraken2-inspect`. `gzip` is handled through Python's `gzip` module, so the standalone `gzip` program is not invoked. Apptainer is not required by this repository; use it only when an external HPC environment supplies Kraken2 through a container.

```bash
cd /path/to/kraken_read_parser
python -m pip install -e '.[dev]'
python -m pytest -q
python -m kraken_read_parser.cli --help
kraken-read-parser --help
```

Use `python -m kraken_read_parser.cli` when working directly from a checkout or when you want to be explicit about the interpreter/environment. Use `kraken-read-parser` after installing the package into the active environment; it is the same `main()` entry point. Confirm `which kraken-read-parser`, `python --version`, and the Git commit on an HPC node rather than assuming login-node and batch environments match.

## D. CLI reference

All commands accept `-h/--help`. The CLI exits 0 after success and 1 after a caught operational/validation exception; argparse usage errors normally exit 2. Paths are resolved to absolute paths by the implementation for `run-kraken` and FASTQ validation (the inspect command resolves the DB when invoking the inspector).

### `validate-fastq`

**Purpose:** full, bounded-memory structural and pairing validation without Kraken2. It reads complete R1 and R2 contents and writes one JSON result. It neither runs Kraken2 nor modifies inputs.

| Argument | Required/default | Meaning |
| --- | --- | --- |
| `--r1 PATH`, `--r2 PATH` | required | Plain FASTQ or `.gz` FASTQ mate files. Compression choice is based only on a `.gz` filename suffix. |
| `--sample-id ID` | required | Used in the JSON filename and metadata. Unlike `run-kraken`, this command currently does not call the shared sample-ID validator; use a conservative safe ID (`[A-Za-z0-9._-]+`) anyway. |
| `--outdir PATH` | required | Created if needed; validation JSON is written here. |
| `--overwrite` | false | Allows replacement of its existing validation JSON. |

Output: `OUTDIR/SAMPLE.fastq_validation.json`. Existing output stops the command before scanning unless `--overwrite` is supplied. A failed scan generally still creates a JSON with `validation_status: "failed"`; it then exits nonzero. It does not prove that Kraken2 will run or that biological content is appropriate.

### `inspect-db`

**Purpose:** validate database directory/core files, run `kraken2-inspect --db DB`, retain its stdout, and save provenance. It does not read FASTQs and does not classify a sample. It is strongly recommended before WGS `run-kraken`, but `run-kraken` independently validates only core DB files and can run without prior inspection.

| Argument | Required/default | Meaning |
| --- | --- | --- |
| `--db PATH` | required | Kraken2 DB directory. Must contain readable nonempty `hash.k2d`, `opts.k2d`, and `taxo.k2d`. |
| `--outdir PATH` | required | Created if necessary for inspection artifacts. |
| `--kraken2-bin NAME/PATH` | `kraken2` | Used only to attempt version capture after successful inspection; it is not the inspector executable. |
| `--kraken2-inspect-bin NAME/PATH` | `kraken2-inspect` | Inspector executable invoked as `BIN --db ABSOLUTE_DB`. |
| `--target-lineage NAME` | repeatable; none | Performs a conservative exact final-name-field match against raw inspect lines and writes an advisory target table. This is database representation only, not lineage parsing. |
| `--overwrite` | false | Allows replacement of all three planned inspection artifacts. |

Missing core files are failures. `taxonomy/nodes.dmp` and `taxonomy/names.dmp` are optional, searched first under `DB/taxonomy/` and then at DB root; their absence becomes a warning because raw classification remains possible. If `kraken2-inspect` is missing or returns nonzero, provenance is written with inspection error details where possible, the raw output/target table are not reliable, and the command fails.

### `run-kraken`

**Purpose:** safely launch Kraken2 on paired input, retain the raw five-column paired output, record provenance, and perform post-run structural/report checks. It does **not** perform an implicit full FASTQ validation; run `validate-fastq` first for WGS inputs.

| Argument | Required/default | Meaning |
| --- | --- | --- |
| `--r1 PATH`, `--r2 PATH` | required | Readable, nonempty regular files. Kraken2 reads them. |
| `--db PATH` | required | Readable/traversable DB directory with required core files. |
| `--sample-id ID` | required | Must match `^[A-Za-z0-9._-]+$`, excluding `.` and `..`; determines all artifact stems. |
| `--outdir PATH` | required | Created and tested writable before launch. |
| `--threads N` | required | Integer at least 1; passed to Kraken2 unchanged. |
| `--kraken2-bin NAME/PATH` | `kraken2` | Executable name or path; must be executable or available on `PATH`. Its `--version` result is recorded (a failed version probe is recorded, not necessarily fatal). |
| `--memory-mapping` | false | Adds Kraken2 `--memory-mapping`. It maps the DB rather than fully loading it into RAM; this can reduce RAM but shifts pressure to database storage I/O. |
| `--report-minimizer-data` | false | Adds Kraken2 `--report-minimizer-data`, asks Kraken2 to write the eight-column enriched report, preserves it as `*.report.minimizer.tsv`, then derives the six-column compatibility report. |
| `--expected-pairs N` | none | Positive integer. Compares it strictly with the root report's total fragments after Kraken2 succeeds. A mismatch makes the run `post_run_validation_failed`. |
| `--check-output-lines N` | `1000` | Positive integer. Parses up to N nonblank raw rows and requires every inspected row to contain paired `|:|` hitlist form. It is a sample sanity check, not a full output reconciliation. |
| `--top-taxa-limit N` | `100` | Positive integer limiting each of direct- and clade-assignment top-taxa lists. |
| `--overwrite` | false | Permits replacing every planned artifact that already exists. Use only for a known disposable sample output directory. |
| `--dry-run` | false | Performs input, output-directory, DB-core-file, output-collision, and Kraken2-executable preflight; prints planned command/files but does not run Kraken2 or write metadata/output artifacts. |

A normal successful run requires nonempty raw/report files, the raw paired-output sanity check, a parseable uniform six- or eight-column report, exactly one `unclassified` taxid-0 accounting row, exactly one root taxid-1 accounting row, nonnegative accounting, and any expected-pair reconciliation. Kraken2 nonzero exits are recorded as `kraken_failed`; post-run checks as `post_run_validation_failed`.

The command intentionally omits Kraken2 `--confidence`, `--quick`, `--classified-out`, `--unclassified-out`, and `--use-names`. This preserves sensitive raw numeric evidence and avoids prematurely dropping, splitting, or replacing identifiers before later policy work. Do not infer that omission provides biological filtering.

## E. `validate-fastq` operational guide

```bash
kraken-read-parser validate-fastq \
  --r1 /path/sample_R1.fastq.gz \
  --r2 /path/sample_R2.fastq.gz \
  --sample-id SAMPLE \
  --outdir /path/results/SAMPLE/validation
```

It reads four-line records, verifies a nonempty `@` header, `+` separator, equal sequence/quality lengths, nonempty overall pair set, equal mate counts, and same ordinal template IDs. It supports plain text and gzip (when the path ends in `.gz`), catches corrupt gzip/read/decode failures, and uses bounded memory. It therefore is I/O-heavy for WGS, but much cheaper than discovering a bad pair after a long Kraken2 job.

For mate comparison only, normalization removes a terminal `/1` or `/2` from the first token, or ignores an Illumina second whitespace token beginning `1:`/`2:`. It preserves all other unusual identifier text. It deliberately does **not** detect whole-file duplicate IDs, because exact WGS-scale duplicate tracking would need unbounded memory or external indexing.

Read JSON fields: `validation_status` is `passed` or `failed`; `pairs.records` is validated pair count; `files.r1/r2.records` and `sequence_bases` are per-mate counts; `inputs` gives scalable path/size/mtime identity; `errors` gives actionable failures; and `read_name_normalization` records the policy/limitation. A nonzero command plus a JSON is an expected validation-failure pattern—read `errors[0].message` rather than treating the JSON's existence as success.

## F. `inspect-db` operational guide

```bash
kraken-read-parser inspect-db \
  --db /path/to/kraken2_db \
  --outdir /path/results/database_inspection
```

The required core files are `hash.k2d`, `opts.k2d`, and `taxo.k2d`; each must be a readable nonempty regular file. The optional dumps are `taxonomy/nodes.dmp` and `taxonomy/names.dmp`, with root-level `nodes.dmp`/`names.dmp` accepted as fallbacks. Missing optional dumps warn in provenance but do not prevent raw Kraken classification. Inspection is DB-content/provenance evidence, **not** sample contamination evidence.

`kraken2-inspect` stdout is retained verbatim in `database.inspect.tsv`. With repeated `--target-lineage NAME`, the target TSV reports only an exact, best-effort final-field name match against inspect output. Current code does not extract matched taxids/ranks/minimizer totals into that table and does not resolve taxonomy/lineages; treat it as an advisory presence check, not a lineage summary.

## G. `run-kraken` operational guide

Simple execution:

```bash
kraken-read-parser run-kraken \
  --r1 /path/sample_R1.fastq.gz \
  --r2 /path/sample_R2.fastq.gz \
  --db /path/to/kraken2_db \
  --sample-id SAMPLE \
  --outdir /path/results/SAMPLE \
  --threads 16
```

Recommended evidence-preservation form when the installed Kraken2 supports enriched reports and storage/I/O planning supports mapping:

```bash
kraken-read-parser run-kraken \
  --r1 /path/sample_R1.fastq.gz \
  --r2 /path/sample_R2.fastq.gz \
  --db /path/to/kraken2_db \
  --sample-id SAMPLE \
  --outdir /path/results/SAMPLE \
  --threads 16 \
  --memory-mapping \
  --report-minimizer-data \
  --expected-pairs 100000
```

The latter is appropriate for a known 100,000-pair subset; do not put `100000` on a full run unless that is truly its expected count. Dry-run before scheduling:

```bash
kraken-read-parser run-kraken --r1 R1 --r2 R2 --db DB --sample-id SAMPLE \
  --outdir OUT --threads 16 --memory-mapping --report-minimizer-data --dry-run
```

Outputs are formed from the literal safe sample ID under `OUTDIR`. Without `--report-minimizer-data`, `--report` points to `SAMPLE.kraken2.report.tsv`. With it, `--report` points to `SAMPLE.kraken2.report.minimizer.tsv`, and the standard report is derived after successful Kraken2 completion. A rerun refuses if *any planned artifact* exists; `--overwrite` only removes that guard—it does not clean stale unplanned files or make a previous failed run valid.

## H. Output artifact reference

| Artifact | Command / format / creation | Use, quick inspection, and absence meaning |
| --- | --- | --- |
| `SAMPLE.fastq_validation.json` | `validate-fastq`; JSON, always attempted after output collision check. | Validation result. `python -m json.tool FILE | less`; `failed`/nonzero means fix inputs before Kraken2. |
| `SAMPLE.kraken2.tsv` | `run-kraken`; raw Kraken2 five-column TSV, produced by Kraken2. | **Authoritative reusable raw evidence.** `head -n 3 FILE`; absent/empty after a zero exit causes post-run failure. |
| `SAMPLE.kraken2.report.tsv` | `run-kraken`; standard six-column Kraken2 report. Direct Kraken output normally; derived compatibility view when minimizer mode is selected. | Accounting/compatibility report, not raw read evidence. `head FILE`; parse/accounting failures make run validation fail. |
| `SAMPLE.kraken2.report.minimizer.tsv` | `run-kraken --report-minimizer-data`; enriched eight-column Kraken2 report. | Preserved enriched report. `awk -F '\t' 'NR==1{print NF}' FILE` should print 8; absent when flag was not requested is normal. |
| `SAMPLE.kraken2.stderr.log` | `run-kraken`; Kraken2 stderr, created immediately before subprocess execution. | First place for Kraken2/DB/runtime errors: `tail -n 100 FILE`. Absence can mean preflight/dry-run stopped before launch. |
| `SAMPLE.run_metadata.json` | Non-dry `run-kraken`; JSON, first written with `running` then atomically updated. | Authoritative run state/provenance. `python -m json.tool FILE | less`; non-`completed` means do not treat run as validated. |
| `SAMPLE.kraken2.summary.json` | Successful post-run parsing before possible expected-pair mismatch is raised. | Report accounting, format, reconciliation, and top taxa. It is non-biological summary data. Inspect with `python -m json.tool`. It may exist despite `post_run_validation_failed` if reconciliation then failed. |
| `SAMPLE.kraken2.top_taxa.tsv` | Successful report parse before possible expected-pair mismatch. | Direct and clade top taxa limited by `--top-taxa-limit`; `column -ts $'\t' FILE | less -S`. It is a summary, not a filtering decision. |
| `database.inspect.tsv` | Successful `inspect-db`; raw `kraken2-inspect` stdout. | Inspect DB composition with `head`/`less`; absent on inspector failure. |
| `database.provenance.json` | `inspect-db`; JSON written after inspection success and attempted on inspector failure. | Core/taxonomy file identities, warnings, versions, argv/timing/stderr. Inspect with `python -m json.tool`. |
| `database.target_lineages.tsv` | `inspect-db`; header plus one row per requested target (or just header). | Best-effort exact-name advisory results. Absence means inspection did not reach successful output writing. |

## I. Metadata and schemas

Implemented schema families are v1: `kraken_read_parser.fastq_validation`, `kraken_read_parser.run_metadata`, `kraken_read_parser.database_provenance`, and `kraken_read_parser.kraken_summary`. `docs/schemas.md` additionally mentions reserved future read-evidence, pair-evidence, and binning-manifest names; they are **not** implemented in `schemas.py` or produced by this version.

Most important provenance is package/Python/platform, resolved input/db paths and size/mtime identities, full argv, executable/version probe, timestamps, output paths, `run_status`, exit code, report accounting, and reconciliation. Identities avoid expensive content hashes—do not silently treat matching size/mtime as cryptographic proof of content identity.

| `run_status` | Meaning / likely cause | Safe next action |
| --- | --- | --- |
| `dry_run` | Preflight-only result, returned/printed but no metadata file is written. | Review argv/paths/resources; run validation subset. |
| `running` | Metadata was written immediately before Kraken2. Scheduler kill, timeout, node failure, or still-running job may leave it. | Check scheduler state and stderr/output timestamps; do not overwrite until the job is known stopped. |
| `kraken_failed` | Kraken2 returned nonzero. | Read stderr and metadata error; fix executable/DB/resource issue, use a new/fresh output directory or intentional overwrite. |
| `post_run_validation_failed` | Kraken2 exited 0 but raw output/report/reconciliation checks failed. | Inspect stderr, raw/report files, metadata error, and expected count before rerun. |
| `completed` | Kraken2 exited 0 and current post-run checks/reconciliation passed. | Preserve raw TSV and provenance; later interpretation may use them. |

A long HPC job can leave metadata in `running`, so artifact existence alone never proves completion.

## J. Safety and staged validation model

| Stage | Proves / does not prove | Cost, reads, DB, outputs |
| --- | --- | --- |
| 1. `python -m pytest -q` | Code's mocked unit expectations pass; not a real Kraken2/DB test. | Low; no WGS inputs/DB; temporary small outputs. |
| 2. `validate-fastq` | Both complete FASTQs are structurally valid and synchronized; not Kraken2 compatibility or biology. | WGS I/O-heavy full read of both files; no DB; small JSON. |
| 3. `inspect-db`/preflight | Required DB files exist and inspector can describe DB; not sample performance or taxonomy interpretation. | Does not read FASTQs; invokes inspector/reads DB as Kraken2 does; inspect text may be modest/large. |
| 4. `run-kraken --dry-run` | Current paths, DB core files, output collision state, and executable are acceptable; not actual Kraken2 execution. | No FASTQ content read; no DB load/map by Kraken2; no artifacts. |
| 5. 100,000-pair subset | Actual executable/container/DB/output pipeline works on a representative bounded input; not full-WGS resource sufficiency. | Reads subset and runs Kraken2; DB load/map; creates evidence artifacts. |
| 6. Full WGS | Full sample execution/result accounting. | Very high I/O/compute/storage; preserve all evidence/provenance. |

For human genomic data, never commit real FASTQs, CRAMs/BAMs, VCFs/GVCFs, databases, raw WGS Kraken outputs, SIF images, or HPC work directories. `.gitignore` is a safeguard, not an authorization or complete data-governance policy; use approved storage/access controls.

## K. Troubleshooting

| Symptom | Likely cause / where to look | Safe check or next action |
| --- | --- | --- |
| R1/R2 missing, unreadable, or wrong kind | Incorrect path, permission, directory instead of file. CLI error; validation JSON may record identity. | `stat -- R1 R2` and verify the intended pair; do not create placeholders. |
| Empty FASTQ | Failed/truncated conversion or wrong file. Validation JSON `errors`. | `wc -c -- R1 R2`; rerun/repair conversion upstream. |
| Invalid sample ID | Unsupported characters, `.` or `..` in `run-kraken`. | Choose a stable safe ID matching `[A-Za-z0-9._-]+`. |
| Existing output refusal | Previous/all planned artifact exists without `--overwrite`. | Review `find OUTDIR -maxdepth 1 -type f -name 'SAMPLE*' -print`; use a new run directory or intentional `--overwrite`. |
| DB path/core-file failure | Bad mount/path or missing/empty `hash.k2d`, `opts.k2d`, `taxo.k2d`. | `for f in hash.k2d opts.k2d taxo.k2d; do stat -- "$DB/$f"; done`. |
| Missing taxonomy dumps | DB lacks optional dumps; provenance warning. | Classification can proceed; do not claim lineage-aware interpretation is available. |
| Kraken2 missing | `--kraken2-bin` not executable/on batch `PATH`. | `command -v kraken2; kraken2 --version`, or pass verified absolute/container wrapper path. |
| `kraken2-inspect` missing | Inspector absent from environment/container. | `command -v kraken2-inspect; kraken2-inspect --version`; fix environment before inspection. |
| Kraken2 nonzero | Resource, DB, input, or executable error. | Read `SAMPLE.kraken2.stderr.log` and metadata `error`; check Slurm accounting. |
| Empty raw TSV | Kraken2 produced no records or wrong inputs/output behavior. | Check stderr and sample input/subset; metadata should be `post_run_validation_failed`. |
| Report parse failure | Report has mixed/wrong columns, bad numerics, or missing required root/unclassified accounting. | Inspect `head -n 20` of the report and metadata error; retain raw evidence for diagnosis. |
| Expected-pair mismatch | Wrong expected count or report total differs. | Compare summary `total_reported_pairs` to validated/subset pair count; correct input/count before rerun. |
| Paired-output sanity failure | Inspected raw rows lack `|:|`, suggesting wrong Kraken mode/output. | Review metadata `command`, raw `head`, and stderr; do not bypass by lowering checks. |
| Slurm killed/timed out | Scheduler limit/node failure; metadata may remain `running`. | `sacct -j JOBID --format=JobID,State,Elapsed,MaxRSS,ExitCode`; preserve logs and ensure process stopped before rerun. |
| RAM or I/O issue | DB loading/mapping/storage saturation. | Compare `--memory-mapping` and local policy; choose resources based on a successful subset and DB filesystem performance. |
| Permission failure | Output/db/input mount permissions. | `namei -l PATH` and write a harmless file only in approved disposable output dir; fix ACL/path selection. |

## L. HPC/MSI-style operational templates

The following are **external-project examples to verify**, not repository defaults:

```bash
PARSER_REPO="/scratch.global/$USER/repos/kraken_read_parser"
RUN_ROOT="/scratch.global/$USER/nhc_testing/full_cram_to_fastq_remaining"
DB="/scratch.global/lanej/poynter/gmkf/kmer_denovo/kraken2_db/k2_NCBI_reference_20251007"
OUT_ROOT="/scratch.global/$USER/nhc_testing/full_kraken_read_parser"
```

Update/check out and record exactly what will run:

```bash
cd "$PARSER_REPO"
git fetch --all --prune
git status --short --branch
git rev-parse HEAD
python -m pip install -e '.[dev]'
python -m pytest -q
python -m kraken_read_parser.cli --help
```

For a sample, first verify exact FASTQ filenames rather than guessing naming conventions, then validate:

```bash
SAMPLE="BS_EXAMPLE"
R1="$RUN_ROOT/$SAMPLE/${SAMPLE}_R1.fastq.gz"   # verify this actual layout
R2="$RUN_ROOT/$SAMPLE/${SAMPLE}_R2.fastq.gz"   # verify this actual layout
kraken-read-parser validate-fastq --r1 "$R1" --r2 "$R2" --sample-id "$SAMPLE" \
  --outdir "$OUT_ROOT/$SAMPLE/validation"
kraken-read-parser inspect-db --db "$DB" --outdir "$OUT_ROOT/database_inspection"
kraken-read-parser run-kraken --r1 "$R1" --r2 "$R2" --db "$DB" --sample-id "$SAMPLE" \
  --outdir "$OUT_ROOT/$SAMPLE" --threads 16 --memory-mapping --report-minimizer-data --dry-run
```

Make a genuine 100,000-pair subset with an approved external method (this repository has no subsetting command), validate that subset, then run the same command with `--expected-pairs 100000`. Check `run_status=completed`, nonempty raw/report artifacts, enriched report (if requested), six-column compatibility report, and summary reconciliation before selecting full-run Slurm time/memory/storage. A later Slurm script should use verified module/container setup, stdout/stderr locations, `--cpus-per-task` matching `--threads`, output capacity for raw TSV, and a unique output directory per sample. Do not submit all three samples from assumptions alone.

## M. External project context (verify; not committed defaults)

* Project scratch root: `/scratch.global/winnett/`.
* Likely parser checkout: `/scratch.global/winnett/repos/kraken_read_parser`.
* Full FASTQ conversion root: `/scratch.global/winnett/nhc_testing/full_cram_to_fastq_remaining`.
* Known samples: `BS_15AFEJE8`, `BS_CJ2YQ5XQ`, `BS_KACZT4PS`.
* Reported completed pair counts: `BS_CJ2YQ5XQ` 440,338,321; `BS_15AFEJE8` 626,625,641; `BS_KACZT4PS` 522,834,452.
* Known externally used DB: `/scratch.global/lanej/poynter/gmkf/kmer_denovo/kraken2_db/k2_NCBI_reference_20251007`.
* Known external CSC/Kraken2 container: `/scratch.global/lanej/1000G/cross_species_contamination/csc.sif`.

These facts were supplied as project context, were not accessed by this documentation task, and must be re-verified for existence, permissions, software versions, FASTQ naming/layout, and current counts before command generation. The repository does not depend on them.

## N. Implemented versus planned

| Feature | Implemented now? | Command/module | Notes |
| --- | --- | --- | --- |
| Paired FASTQ validation | Yes | `validate-fastq`, `fastq.py` | Structural/full synchronized scan. |
| Kraken2 execution | Yes | `run-kraken`, `kraken.py` | Paired raw TSV/report preservation. |
| Memory mapping | Yes | `run-kraken --memory-mapping` | Passed directly to Kraken2. |
| Database inspection | Yes | `inspect-db`, `database.py` | Preflight, raw inspect/provenance; no taxonomy resolver. |
| Minimizer-enriched reports | Yes | `--report-minimizer-data` | Requires supporting Kraken2; derives standard report. |
| Expected-pair reconciliation | Yes | `--expected-pairs` | Strictly compares report root total. |
| Report summaries | Yes | `summary.json`, `top_taxa.tsv` | Non-biological accounting/top taxa. |
| Read-level evidence table | No | planned only | Raw Kraken TSV is retained, but no derived evidence table. |
| Pair-level evidence table | No | planned only | No pair scoring/labels. |
| Lineage-aware interpretation | No | planned only | Optional dumps are only detected. |
| Human/nonhuman labels | No | planned only | Never use current output as final filter. |
| FASTQ binning | No | planned only | No human/nonhuman/uncertain/discordant bins. |
| Taxon extraction | No | planned only | No extraction command. |
| Nextflow workflow | No | planned only | No workflow files in repository. |
| Downstream SNV/indel integration | No | planning only | No caller integration. |

## O. Command-generation checklist

Before generating commands for real data, answer each item from current evidence:

1. What branch/commit is checked out (`git branch --show-current`; `git rev-parse HEAD`)?
2. What version/package environment does the CLI report or install expose?
3. Are tests passing in that environment?
4. Are R1/R2 paths, permissions, names, and intended sample identity verified?
5. Has `validate-fastq` passed for the exact files?
6. Is the database path and all three core files verified on the compute filesystem?
7. Has `inspect-db` passed with the actual inspector/container?
8. Are expected pair counts known and appropriate for each exact input/subset?
9. Is the output directory fresh, or is `--overwrite` demonstrably intentional?
10. Is `--memory-mapping` needed after considering node RAM and DB-storage I/O?
11. Is `--report-minimizer-data` supported by the actual Kraken2 version and desired?
12. Has a 100,000-pair validation completed with `run_status=completed`?
13. Are full-run Slurm resources, disk capacity, walltime, and thread settings chosen from evidence?
14. Are scheduler stdout/stderr, `SAMPLE.kraken2.stderr.log`, metadata, and output paths known?
15. What exact artifact/status/reconciliation values count as success, and what stop/review condition counts as failure?

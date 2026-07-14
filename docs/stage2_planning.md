# Stage 2 implementation playbook

This document records the completed Stage 2 repository review and staged implementation plan for `sashawin7/kraken_read_parser`. It is intended to be self-contained so that future Codex or developer sessions can implement the next major phase without needing the original planning chat.

The project is part of a broader non-human contamination bioinformatics effort. The long-term scientific question is:

> Does identifying and removing sequencing read pairs with credible non-human taxonomic evidence before human alignment reduce false-positive SNV/indel and structural-variant calls without damaging real human variant signal?

The intended production workflow is FASTQ-first:

```text
Raw paired-end human genomic FASTQ
→ Kraken2 classification
→ read- and pair-level evidence interpretation
→ human/non-human/uncertain/discordant labeling
→ optional user-configured filtering
→ paired FASTQ outputs
→ human alignment
→ SNV/indel and SV calling
→ filtered-versus-unfiltered comparison
```

The parser must be designed for paired FASTQ files that have never been aligned. BAM, CRAM, genomic coordinates, existing variant calls, and human-alignment metadata must not be required inputs for normal operation.

---

## 1. Current repository assessment

### 1.1 Review scope and source-of-truth findings

The Stage 2 review inspected the repository source, CLI entry point, Kraken runner, parser, validation helpers, tests, packaging config, README, tracked sample data, `.gitignore`, and recent git history. The repository currently matches the intended Stage 1 description closely: it is a small Python package centered on reproducible paired-end Kraken2 execution and preservation/parsing of raw Kraken2 output, not yet an evidence interpretation or FASTQ filtering tool.

Commands used during the review included:

```bash
find /workspace -name AGENTS.md -print -maxdepth 4
git status --short
git log --oneline -5
git ls-files
find . -maxdepth 3 -type f | sort
sed -n '1,240p' README.md
sed -n '1,220p' pyproject.toml
nl -ba kraken_read_parser/*.py tests/*.py README.md pyproject.toml .gitignore
zcat normal_R1.fastq.gz | sed -n '1,8p'
python -m pytest -q
```

No `AGENTS.md` files were found under `/workspace` during that review.

### 1.2 What is already usable

#### Package and CLI foundation

The package is installable as `kraken-read-parser` and exposes one console-script entry point:

```text
kraken-read-parser = kraken_read_parser.cli:main
```

It requires Python 3.9+ and currently has only `pytest` as a development dependency.

The CLI currently has a single subcommand, `run-kraken`, with required paired FASTQ inputs, Kraken2 database path, sample id, output directory, and thread count. The CLI catches exceptions, prints a concise `ERROR: ...` message to stderr, and exits nonzero.

#### Kraken2 command construction and artifact preservation

The runner constructs a paired-end Kraken2 command using `--paired`, `--db`, `--threads`, `--output`, and `--report`, followed by R1 and R2 paths. This agrees with the README’s documented command contract.

For each sample, Stage 1 plans four artifacts:

- raw per-read Kraken2 TSV;
- Kraken2 report TSV;
- stderr log;
- run metadata JSON.

The runner validates that R1, R2, and the database path exist, creates the output directory, protects existing outputs unless `--overwrite` is used, verifies the Kraken2 executable, runs Kraken2 with stderr captured to a file, writes metadata, checks that expected output/report files exist and are non-empty, then sanity-checks the Kraken2 output.

The metadata currently records package/Python/platform information via `base_metadata`. The runner adds sample id, absolute input/database/output paths, thread count, executable, command argv, start time, output paths, dry-run status, end time, elapsed seconds, and exit code.

#### Streaming parser seam

The parser models one Kraken2 output row as a frozen dataclass with raw fields and paired-read convenience fields. It expects Kraken2’s five tab-delimited fields: status, read id, taxid, length, and raw hitlist. It splits paired mate lengths on `|` and mate hitlists on `|:|`.

The parser is streaming: `parse_kraken2` yields records from any iterable of lines, and `parse_kraken2_file` opens and streams a file path. This is a useful seam for Stage 2 because WGS-scale Kraken output must not require whole-file memory loading.

#### Sanity checking of paired Kraken2 output

`sanity_check_output` parses up to a configurable number of records, rejects empty Kraken2 output, and by default requires each checked row to contain `|:|` in the hitlist field, which indicates paired Kraken2 evidence. This is a good Stage 1 guard but should become more nuanced later because valid evidence parsing should distinguish Kraken2 paired-output shape, FASTQ pair integrity, and biological interpretation.

#### Tests

The current tests are focused and fast. They cover:

- CLI parsing and dry-run behavior;
- Kraken2 command construction, including the deliberate absence of `--classified-out` and `--confidence`;
- overwrite protection, dry runs, mocked successful runs with metadata, and mocked failed runs;
- parser behavior for valid paired rows, malformed rows in strict/non-strict modes, absent mate separators, and sanity-check rejection of unpaired output.

The reviewed baseline test suite passed with:

```text
12 passed in 0.09s
```

#### Documentation and sample data

The README accurately documents Stage 1’s limited scope: paired-end Kraken2 execution, artifact preservation, and a parser seam. It explicitly states that Stage 1 does not compute final human/nonhuman scores, write FASTQ bins, parse FASTQ sequence content, query Kraken2 databases directly, or hard-code taxonomy thresholds.

The README also correctly warns that included FASTQs are development examples only, not benchmarks or threshold evidence. The repository includes compressed `normal_R1.fastq.gz`/`normal_R2.fastq.gz` examples and uncompressed toy `mutant_R1.fastq`/`mutant_R2.fastq` examples.

`.gitignore` excludes result directories and Stage 1 Kraken2 artifacts but does not yet exclude broad Stage 2/HPC outputs such as binned FASTQs, Parquet/Arrow evidence tables, Nextflow work directories, Apptainer images, or external real-data proof-of-concept paths.

### 1.3 What is only scaffolded or intentionally absent

The current repository has no modules for:

- FASTQ parsing/validation beyond path existence;
- gzip output writing;
- read-name normalization;
- pair synchronization checks;
- taxonomy loading from `nodes.dmp`/`names.dmp`;
- Kraken2 hitlist/evidence metric parsing beyond preserving the raw string;
- read-level or pair-level labels;
- policy configuration;
- FASTQ binning;
- taxonomic summaries;
- reusable interpretation from existing Kraken2 output;
- schema versioning;
- CI workflows;
- container or workflow orchestration;
- downstream variant-caller integration documentation.

These gaps are consistent with the README’s Stage 1 limitations.

### 1.4 Current architectural seams worth preserving

The following should be preserved and extended rather than replaced:

1. **Raw Kraken2 output as first-class evidence.** The runner already writes `SAMPLE_ID.kraken2.tsv` and does not force Kraken2’s own classified/unclassified FASTQ outputs.
2. **Streaming parser.** The parser already exposes an iterator over records.
3. **Dry-run support.** Dry-run returns planned metadata and prints the command/output files without writing metadata.
4. **Simple package layout.** The repository is small enough that Stage 2 can add well-bounded modules without large refactors.
5. **Tests that avoid a real Kraken2 database by default.** This is critical for CI and should remain the default test mode.

### 1.5 Current behavior that may constrain the next phase

1. **No explicit schema versioning.** Metadata has package version but no schema version.
2. **No input content validation.** Stage 1 only checks that input paths exist.
3. **No sample-id validation.** Output filenames are derived directly from `sample_id`.
4. **No taxonomy/database validation.** Any existing path is accepted as `--db`.
5. **No structured error types.** CLI catches all exceptions and prints a generic message.
6. **No output manifest.** The runner returns output paths in metadata but does not write a separate reconciliation manifest for later interpretation/binning.
7. **No CI workflow.** There are tests, but no tracked `.github/workflows` files were found during review.

---

## 2. Gap analysis against the target behavior

### 2.1 FASTQ-first requirement

The repository is currently FASTQ-first in the sense that `run-kraken` accepts paired FASTQ paths and does not accept BAM/CRAM/variant inputs. However, it is not yet a full FASTQ processing tool because it does not inspect FASTQ contents, validate pair synchronization, or write filtered paired FASTQ outputs.

### 2.2 Evidence-rich interpretation

Current evidence preservation is limited to the raw Kraken2 TSV, report, stderr log, and basic run metadata. The parser exposes raw hitlist strings but does not parse taxon/count tokens, informative k-mer counts, human evidence, non-human evidence, or competing evidence.

### 2.3 Taxonomy-aware classification

There is no taxonomy module and no `nodes.dmp`/`names.dmp` handling. This is the largest scientific gap. The plan must avoid a simplistic “taxid != 9606 means non-human” approach.

The `jlanej/nonhuman-screen` methodology is directly relevant as a conceptual and scientific reference: it uses lineage-aware classification, treats human ancestors/root/broad eukaryotic assignments differently from true non-human assignments, applies a human-homology guard based on per-read k-mer detail, tracks UniVec-Core separately, and warns that missing taxonomy corrupts results in both directions. Its database documentation also recommends Kraken2 database validation for index files plus `nodes.dmp` and `names.dmp`; without taxonomy dumps it falls back to exact-taxid behavior that is scientifically unsafe for gating decisions.

This project should not blindly copy that implementation. If reuse or adaptation is recommended in a future PR, the implementer must account for licensing, attribution, compatibility, maintainability, and whether a dependency or independent implementation is more appropriate.

### 2.4 Configurable policies and safe defaults

Current Stage 1 intentionally does not pass Kraken2 `--confidence` and does not hard-code taxonomy thresholds. That is appropriate for preserving raw evidence, but Stage 2 needs explicit policy files and recorded thresholds for interpretation/action.

### 2.5 Pair-level action

The parser can detect paired Kraken2 hitlists, but it does not reconcile Kraken records with actual R1/R2 FASTQ records and does not make pair-level decisions. The future system must make the pair the primary action unit and never write R1 and R2 to different final bins.

### 2.6 Output bins and taxonomic organization

There is no binning. Future output must produce synchronized paired FASTQs for downstream alignment. The scalable strategy should avoid creating one FASTQ pair per observed taxid by default. Instead, top-level action bins should be FASTQ files, and taxonomic organization should primarily live in a machine-readable evidence table plus optional, user-selected extraction commands.

### 2.7 Provenance and auditability

Current metadata is a good start but incomplete for Stage 2. It lacks:

- input content hashes or at least size/mtime identity;
- Kraken2 version capture;
- database hash/provenance;
- taxonomy file identity;
- policy/config hash;
- schema versions;
- output counts by bin;
- reconciliation totals;
- resource usage where available.

### 2.8 HPC and downstream integration

No Nextflow, Apptainer, SLURM, or downstream integration exists. This should be added only after the core CLI can validate FASTQs, interpret evidence, and write stable output contracts.

---

## 3. Recommended target user workflow

The next phase should expose a staged CLI that separates expensive Kraken2 classification from cheaper interpretation and binning.

### 3.1 Validate paired FASTQ inputs

```bash
kraken-read-parser validate-fastq \
  --r1 sample_R1.fastq.gz \
  --r2 sample_R2.fastq.gz \
  --sample-id SAMPLE \
  --outdir results/SAMPLE
```

Outputs:

- `SAMPLE.fastq_validation.json`
- optional `SAMPLE.fastq_validation.tsv` for per-file summary;
- clear failure if malformed, truncated, unsynchronized, empty, or count-mismatched.

### 3.2 Run Kraken2 once and preserve raw output

Keep the existing command, with backward-compatible behavior:

```bash
kraken-read-parser run-kraken \
  --r1 sample_R1.fastq.gz \
  --r2 sample_R2.fastq.gz \
  --db /path/to/kraken2_db \
  --sample-id SAMPLE \
  --outdir results/SAMPLE \
  --threads 32
```

Outputs should remain compatible with Stage 1:

- `SAMPLE.kraken2.tsv`
- `SAMPLE.kraken2.report.tsv`
- `SAMPLE.kraken2.stderr.log`
- `SAMPLE.run_metadata.json`

Enhance metadata rather than changing these names immediately.

### 3.3 Validate database/taxonomy

```bash
kraken-read-parser inspect-db \
  --db /path/to/kraken2_db \
  --outdir results/SAMPLE \
  --sample-id SAMPLE
```

Outputs:

- `SAMPLE.database_provenance.json`
- `SAMPLE.taxonomy_summary.tsv`
- clear status for `nodes.dmp`, `names.dmp`, human lineage, UniVec/synthetic representation, and user-requested target lineages.

### 3.4 Interpret evidence from reusable Kraken2 output

```bash
kraken-read-parser interpret \
  --kraken2-tsv results/SAMPLE/SAMPLE.kraken2.tsv \
  --r1 sample_R1.fastq.gz \
  --r2 sample_R2.fastq.gz \
  --db /path/to/kraken2_db \
  --policy policies/default_sensitive.yaml \
  --sample-id SAMPLE \
  --outdir results/SAMPLE
```

Outputs:

- read-level evidence table;
- pair-level evidence/action table;
- summary JSON;
- reconciliation JSON;
- provenance JSON;
- no FASTQ binning unless requested.

### 3.5 Apply policy and write paired FASTQ bins

```bash
kraken-read-parser bin-fastq \
  --pair-evidence results/SAMPLE/SAMPLE.pair_evidence.tsv.gz \
  --r1 sample_R1.fastq.gz \
  --r2 sample_R2.fastq.gz \
  --policy policies/default_sensitive.yaml \
  --sample-id SAMPLE \
  --outdir results/SAMPLE/bins
```

Default output bins:

```text
bins/
  SAMPLE.human.R1.fastq.gz
  SAMPLE.human.R2.fastq.gz
  SAMPLE.nonhuman.R1.fastq.gz
  SAMPLE.nonhuman.R2.fastq.gz
  SAMPLE.uncertain.R1.fastq.gz
  SAMPLE.uncertain.R2.fastq.gz
  SAMPLE.discordant.R1.fastq.gz
  SAMPLE.discordant.R2.fastq.gz
  SAMPLE.synthetic_vector.R1.fastq.gz
  SAMPLE.synthetic_vector.R2.fastq.gz
  SAMPLE.binning_manifest.json
```

For downstream SNV/indel comparison, the key contract is:

- `human.R1/R2.fastq.gz` = kept/filtered human-bin FASTQs for alignment;
- original R1/R2 = unfiltered comparison input;
- all other bins are review/recovery outputs, not silently discarded.

### 3.6 Optional taxon-specific extraction

```bash
kraken-read-parser extract-taxon \
  --pair-evidence SAMPLE.pair_evidence.tsv.gz \
  --r1 sample_R1.fastq.gz \
  --r2 sample_R2.fastq.gz \
  --taxid 9850 \
  --include-descendants \
  --out-prefix SAMPLE.cervidae_or_target
```

This avoids unbounded FASTQ-file proliferation while still supporting taxonomic inspection and recovery.

---

## 4. Important scientific and product decisions

### 4.1 Safest default filtering behavior

**Recommendation:** Default to evidence/report-only interpretation unless the user explicitly invokes binning or a `--write-bins`/`bin-fastq` command. When binning is invoked, the safest default downstream “human” FASTQ should include `human`, `unclassified`, and `uncertain` pairs, and exclude only policy-confident `nonhuman` and separately classified `synthetic_vector` pairs. `discordant` pairs should default to a separate review bin and not be silently discarded from the primary human output until validation shows this is safe.

**Rationale:**

- Software-engineering principle: no silent data loss.
- Scientific practice: weak/broad/conflicting Kraken2 evidence should not destroy human coverage before validation.
- Empirical threshold: exact non-human removal threshold requires miniCRAM-derived and later WGS validation.

### 4.2 User-facing classification vocabulary

Use stable pair-level labels:

- `human_consistent`
- `nonhuman_confident`
- `uncertain_low_evidence`
- `discordant_human_nonhuman`
- `unclassified`
- `synthetic_vector`

Also expose a higher-level `action` field, separate from label:

- `keep_for_human_alignment`
- `remove_from_human_alignment`
- `review`
- `write_synthetic_vector_bin`

This preserves the separation between evidence, interpretation, and action.

### 4.3 Scalable taxonomic sub-binning

**Recommendation:** Do not create one FASTQ pair per taxid by default. Write:

1. top-level synchronized FASTQ bins;
2. pair/read evidence tables with assigned taxid, rank, lineage, broad domain, and best lineage bucket;
3. summaries by taxid/rank/domain;
4. optional `extract-taxon` command for user-selected taxa or lineages.

This supports WGS scale and avoids millions of tiny files or file-handle exhaustion.

### 4.4 First stable evidence schema

Use two stable, versioned schemas.

#### 4.4.1 Read-level evidence table: `read_evidence.schema_version = 1`

Recommended columns:

- `sample_id`
- `pair_id`
- `mate` (`R1`/`R2`)
- `original_read_id`
- `normalized_read_id`
- `kraken_status`
- `assigned_taxid`
- `assigned_name`
- `assigned_rank`
- `assigned_lineage_taxids`
- `assigned_lineage_names`
- `broad_domain`
- `is_human_clade`
- `is_human_lineage_or_broad_ancestor`
- `is_nonhuman_candidate`
- `is_synthetic_vector`
- `is_unclassified`
- `read_length`
- `mean_base_quality`
- `min_base_quality`
- `q20_fraction`
- `q30_fraction`
- `n_count`
- `n_fraction`
- `low_complexity_flag`
- `kraken_hitlist_raw`
- `human_kmer_count`
- `assigned_taxon_kmer_count`
- `nonhuman_kmer_count`
- `informative_kmer_count`
- `total_kmer_count`
- `human_homology_guard`
- `read_reason_codes`

#### 4.4.2 Pair-level evidence table: `pair_evidence.schema_version = 1`

Recommended columns:

- `sample_id`
- `pair_id`
- `r1_original_read_id`
- `r2_original_read_id`
- `r1_assigned_taxid`
- `r2_assigned_taxid`
- `pair_best_taxid`
- `pair_best_name`
- `pair_best_rank`
- `pair_broad_domain`
- `mate_agreement`
- `has_human_evidence`
- `has_nonhuman_evidence`
- `has_synthetic_vector_evidence`
- `has_unclassified_mate`
- `r1_label`
- `r2_label`
- `pair_label`
- `policy_name`
- `policy_version`
- `policy_hash`
- `action`
- `action_reason_codes`
- `thresholds_triggered`
- `r1_quality_flags`
- `r2_quality_flags`

Use TSV.GZ as the first stable format because it is easy for Python, R, and command-line tools. Optionally add Parquet later after dependency review.

### 4.5 Schema evolution

Every machine-readable output should include:

- explicit `schema_name`;
- integer `schema_version`;
- package version;
- policy name/version/hash;
- database/taxonomy provenance reference.

Breaking schema changes require a new version. Additive columns can remain within the same major schema if documented, but tests should enforce required columns.

### 4.6 Raw Kraken2 output as reusable intermediate

**Recommendation:** Treat raw Kraken2 TSV as a reusable, immutable intermediate. Interpretation and binning should be rerunnable without rerunning Kraken2 if inputs, database taxonomy, and raw Kraken output are unchanged.

This is supported by the current Stage 1 design, which already preserves raw output and metadata.

### 4.7 Missing taxonomy behavior

If `nodes.dmp` is unavailable or invalid, the tool should:

- allow `run-kraken` to complete;
- allow `inspect-db` to report failure/warning;
- allow raw evidence parsing;
- **not** allow confident `nonhuman_confident` labels by default;
- label interpretation as `taxonomy_unavailable`;
- set actions to `review` or `keep_for_human_alignment`, not removal.

Missing taxonomy makes lineage-aware classification unreliable in both directions.

### 4.8 Discordant pair representation

Represent discordance at pair level, never by splitting mates into different final action bins. The pair-level table should preserve both mate labels and a pair label such as `discordant_human_nonhuman`. FASTQ binning should write both mates together to the discordant bin.

### 4.9 First-release configuration versus deferred configuration

#### Configure in first Stage 2 release

- policy name/version;
- Kraken confidence if project chooses to pass it in future runs, but default should preserve current Stage 1 behavior unless changed deliberately;
- minimum informative k-mer fraction/count;
- minimum read length for confident calls;
- base-quality warning thresholds;
- low-complexity warning threshold;
- treatment of discordant pairs;
- treatment of unclassified pairs;
- treatment of synthetic/vector pairs;
- target lineages to highlight in summaries;
- output compression level.

#### Defer

- machine-learning scoring;
- variant-aware thresholds;
- locus/coverage-aware filtering decisions;
- SV-caller-specific policy;
- automatic per-cohort threshold optimization;
- automatic database download/build;
- taxon-specific default removal beyond broad safe categories.

### 4.10 Validation of artifact reduction without destroying coverage

For the proof of concept, evaluate filtered versus unfiltered outputs by:

- running both through identical downstream SNV/indel settings;
- confirming candidate false-positive variant support decreases;
- confirming local total depth and reference/alternate balance are not globally destroyed;
- tracking how many reads/pairs are removed and their labels;
- checking that removed pairs have credible non-human evidence rather than merely low quality or unclassified status;
- recording whether the suspected hoofed-animal signal appears in Cervidae/Ruminantia/Artiodactyla-related lineages.

This is empirical validation, not a hard-coded parser rule.

### 4.11 Decision categories

#### Decisions based mostly on software-engineering principles

- Keep raw Kraken2 output as a reusable intermediate.
- Separate evidence, interpretation, and action.
- Make schemas explicit and versioned.
- Avoid unbounded per-taxid FASTQ file generation.
- Preserve original FASTQ headers and paired synchronization.
- Keep core CLI independent of workflow orchestration.
- Fail loudly on malformed or unreconciled inputs.

#### Decisions supported by common scientific practice

- Use lineage-aware taxonomy rather than exact-taxid-only logic.
- Do not treat all non-9606 assignments as non-human.
- Treat weak, broad, or conflicting evidence as uncertain/review rather than forcing a definitive label.
- Preserve raw and derived evidence for later threshold review.
- Treat pair as the primary filtering unit.

#### Thresholds requiring empirical validation

- Minimum informative k-mer count or fraction for confident non-human evidence.
- Human-homology guard threshold.
- Minimum read length for confident classification.
- Quality/complexity thresholds for uncertainty flags.
- Whether discordant pairs should be excluded from the default downstream human FASTQ.

#### Questions requiring project-owner or domain-expert input

- Which Kraken2 database should be the first recommended validation database?
- Whether to pass Kraken2 `--confidence` in Stage 2 runs or preserve current no-confidence behavior.
- Which target lineages should be highlighted by default beyond cervid/ruminant/artiodactyl examples.
- What local coverage preservation criterion is acceptable in the proof of concept.
- How conservative the first default removal policy should be after empirical validation.

---

## 5. Staged PR playbook

The plan keeps the next major phase below five PRs. Four coherent PRs are recommended.

### 5.1 PR 1 — Stage 2 foundations: FASTQ integrity, schemas, provenance, and CLI separation

#### Concise title

**Stage 2 foundations: FASTQ integrity, schemas, provenance, and CLI separation**

#### Primary goal

Establish the non-biological foundations needed for safe evidence interpretation: robust FASTQ validation, read-name normalization, explicit schemas, richer provenance, and CLI structure that separates validation, Kraken execution, interpretation, and binning.

#### Why it belongs at this stage

Before adding taxonomy and filtering logic, the tool must prove it can safely account for paired FASTQ inputs at scale. Pair synchronization and schema/provenance decisions are prerequisites for every later PR.

#### User-visible capabilities added

- New `validate-fastq` command.
- Gzip and plain FASTQ input support.
- Mate synchronization checks.
- Read-name normalization report.
- Malformed/truncated FASTQ detection.
- Sequence/quality length consistency checks.
- Empty input and mismatched record-count errors.
- Initial schema definitions and documentation.
- Enhanced run metadata with schema versions and input file identity.

#### Scope

Likely implementation modules:

- `kraken_read_parser/fastq.py`
- `kraken_read_parser/readnames.py`
- `kraken_read_parser/schemas.py`
- `kraken_read_parser/provenance.py`
- updates to `kraken_read_parser/cli.py`
- updates to `kraken_read_parser/metadata.py`
- tests under `tests/`

Specific work:

- Implement streaming FASTQ reader that supports `.gz` and uncompressed files.
- Validate four-line FASTQ records.
- Verify headers start with `@` and separator line starts with `+`.
- Verify sequence and quality length equality.
- Normalize read names by removing `/1`, `/2`, whitespace suffixes, and common Illumina mate decorations while preserving original ids.
- Detect R1/R2 normalized id mismatch at the same ordinal.
- Count records and bases.
- Compute lightweight per-file summaries.
- Add duplicate-id detection as optional bounded mode:
  - exact full duplicate detection for small files/tests;
  - WGS-scale warning mode using configurable first-N check or optional Bloom/filter later.
- Add schema version constants for:
  - validation summary;
  - run metadata;
  - future read evidence;
  - future pair evidence;
  - binning manifest.
- Extend `.gitignore` for Stage 2/HPC outputs:
  - `*.fastq.gz` outputs under results;
  - `*.pair_evidence.tsv.gz`;
  - `*.read_evidence.tsv.gz`;
  - `*.summary.json`;
  - `*.manifest.json`;
  - `work/`;
  - `.nextflow*`;
  - `*.sif`;
  - external proof-of-concept data directories.
- Preserve existing `run-kraken` filenames and behavior.

#### Explicit out-of-scope items

- Taxonomy interpretation.
- Non-human labels.
- FASTQ binning.
- Nextflow/Apptainer.
- Changes to biological thresholds.
- Real miniCRAM-derived data.

#### Important compatibility considerations

- Existing `run-kraken` command must continue to pass all current tests.
- Existing output artifact names must remain unchanged.
- `run-kraken` should not require full FASTQ validation by default in this PR, but should optionally accept `--validate-inputs` or document the new separate validation step.
- Dry-run behavior should remain compatible.

#### Major repository areas likely to be affected

- `kraken_read_parser/cli.py`
- `kraken_read_parser/metadata.py`
- `kraken_read_parser/validation.py`
- new FASTQ/read-name/schema/provenance modules
- `README.md`
- `.gitignore`
- `tests/`

#### Required unit, integration, functional, and regression tests

Unit tests:

- FASTQ reader parses gzip and plain FASTQ.
- Rejects truncated records.
- Rejects missing `@`.
- Rejects invalid/missing `+`.
- Rejects sequence/quality length mismatch.
- Handles empty files.
- Normalizes read ids:
  - `read/1` and `read/2`;
  - Illumina whitespace mate fields;
  - no suffix;
  - unusual but valid ids.
- Detects R1/R2 mismatch.
- Detects count mismatch.
- Computes base/record counts.

Integration tests:

- Run `validate-fastq` on included normal gzipped examples.
- Run `validate-fastq` on included uncompressed mutant toy examples.
- Verify JSON output schema and required fields.

Functional tests:

- CLI exits `0` for valid fixture pairs.
- CLI exits nonzero with actionable error for malformed fixture.
- `run-kraken` dry-run remains unchanged.

Regression tests:

- Current parser and Kraken command tests continue passing.

#### Documentation updates

- Add “Stage 2 architecture overview.”
- Add FASTQ validation command usage.
- Document read-name normalization.
- Document that sample FASTQs are development examples only.
- Add output schema docs under `docs/schemas/`.
- Add “data that must not be committed” guidance.

#### Acceptance criteria

- `python -m pytest -q` passes.
- `kraken-read-parser validate-fastq` works on gzip and plain examples.
- Invalid FASTQ fixtures fail with specific errors.
- No current `run-kraken` behavior is broken.
- Schema version constants appear in validation output.
- `.gitignore` covers obvious Stage 2 large/generated outputs.

#### Dependencies on earlier PRs

None.

#### Major scientific or operational risks

- Read-name normalization can be too aggressive and collapse distinct reads.
- Duplicate detection can accidentally become memory-unbounded.
- Strict validation could reject real-world FASTQ header variants.

#### Rollback or partial deployment

Rollback is easy because PR 1 should not alter biological interpretation. If validation proves too strict, keep the modules and relax CLI defaults while retaining warnings.

#### Repository capability after merge

The repository can safely validate paired FASTQ integrity and produce machine-readable validation/provenance outputs while preserving all Stage 1 Kraken2 behavior.

### 5.2 PR 2 — Lineage-aware taxonomy and evidence interpretation from reusable Kraken2 output

#### Concise title

**Lineage-aware taxonomy and evidence interpretation from reusable Kraken2 output**

#### Primary goal

Convert raw Kraken2 output plus FASTQ-derived quality metrics into versioned read-level and pair-level evidence tables using safe lineage-aware taxonomy logic.

#### Why it belongs at this stage

Biological interpretation must be correct before any FASTQ filtering action is taken. This PR should produce evidence and labels but not yet write filtered FASTQ bins by default.

#### User-visible capabilities added

- New `inspect-db` command.
- New `interpret` command.
- Taxonomy validation using Kraken2 database taxonomy files.
- Human lineage awareness.
- Synthetic/vector handling.
- Read-level evidence table.
- Pair-level evidence table.
- Summary and reconciliation reports.
- Configurable policy file with recorded thresholds.
- Missing-taxonomy safe behavior.

#### Scope

Likely implementation modules:

- `kraken_read_parser/taxonomy.py`
- `kraken_read_parser/evidence.py`
- `kraken_read_parser/policy.py`
- `kraken_read_parser/quality.py`
- `kraken_read_parser/interpret.py`
- additions to CLI.

Specific work:

- Locate and parse `nodes.dmp` and `names.dmp` from:
  - `DB/taxonomy/nodes.dmp`;
  - `DB/taxonomy/names.dmp`;
  - fallback root-level files if documented.
- Validate Kraken2 DB index files such as `hash.k2d`, `opts.k2d`, `taxo.k2d`, following the conceptual `nonhuman-screen` database validation approach.
- Build child-to-parent lineage lookup.
- Identify:
  - human clade rooted at 9606;
  - human lineage ancestors up to root;
  - broad eukaryotic/ancestor assignments;
  - bacteria, archaea, fungi, viruses, plants, protists where taxonomy supports it;
  - synthetic/vector/UniVec-like entries when represented.
- Parse Kraken2 hitlist tokens sufficiently to count:
  - assigned taxon k-mer evidence;
  - human k-mer evidence;
  - non-human candidate k-mer evidence;
  - total/informative k-mer evidence.
- Apply a human-homology guard conceptually similar to `nonhuman-screen`: if a read has meaningful human k-mer evidence, do not confidently call it non-human without policy support.
- Compute read quality summaries from FASTQ:
  - length;
  - mean quality;
  - min quality;
  - Q20/Q30 fraction;
  - N count/fraction;
  - lightweight low-complexity flag.
- Join FASTQ pairs and Kraken2 records by normalized read id, with strict reconciliation.
- Produce `read_evidence.tsv.gz` and `pair_evidence.tsv.gz`.
- Produce `interpret_summary.json` and `reconciliation.json`.
- Record policy/config in provenance, including policy hash.
- Include reason codes, e.g.:
  - `TAXONOMY_UNAVAILABLE`;
  - `UNCLASSIFIED_BY_KRAKEN`;
  - `ASSIGNED_HUMAN_CLADE`;
  - `ASSIGNED_HUMAN_LINEAGE_ANCESTOR`;
  - `NONHUMAN_LINEAGE_SUPPORTED`;
  - `HUMAN_KMER_GUARD`;
  - `LOW_INFORMATIVE_KMER_COUNT`;
  - `LOW_QUALITY`;
  - `MATE_CONFLICT`;
  - `SYNTHETIC_VECTOR`.

#### Explicit out-of-scope items

- Writing filtered FASTQ bins.
- Nextflow/HPC orchestration.
- Downstream variant-caller execution.
- Automatic database download/build.
- Final empirically validated thresholds.
- Copying `nonhuman-screen` implementation.

#### Important compatibility considerations

- Raw Kraken2 TSV must remain accepted as a reusable intermediate.
- Stage 1 `run-kraken` output names remain unchanged.
- If taxonomy is missing, interpretation should not crash by default unless user requests `--require-taxonomy`; instead, produce safe `taxonomy_unavailable`/review labels and no confident removals.
- The parser’s existing raw-field preservation should remain.

#### Major repository areas likely to be affected

- New taxonomy/evidence/policy/quality modules.
- `parser.py` may gain hitlist-token helpers while preserving current `KrakenRecord`.
- CLI.
- README and new docs.
- Tests with synthetic taxonomy fixtures.

#### Required unit, integration, functional, and regression tests

Unit tests:

- Parse minimal `nodes.dmp`/`names.dmp`.
- Build lineage from taxid to root.
- Identify human clade and human-lineage ancestor assignments.
- Avoid treating every non-9606 taxid as non-human.
- Identify bacteria/viral/fungal/etc. descendants in tiny taxonomy fixture.
- Handle missing names.
- Handle missing taxonomy files.
- Parse Kraken2 hitlist strings with:
  - normal taxid counts;
  - mate separator;
  - ambiguous/unclassified tokens;
  - malformed tokens.
- Apply human-homology guard.
- Compute FASTQ quality metrics.

Integration tests:

- Synthetic paired FASTQ + synthetic Kraken2 TSV + synthetic taxonomy:
  - human/human pair;
  - nonhuman/nonhuman pair;
  - unclassified pair;
  - one human mate and one nonhuman mate;
  - synthetic/vector pair;
  - low-evidence pair.
- Verify output tables contain required schema columns.
- Verify reconciliation counts sum to input pair count.

Functional tests:

- `inspect-db` succeeds on minimal fake DB.
- `interpret` can run without real Kraken2.
- `interpret` rejects Kraken/FASTQ read-id mismatches.

Regression tests:

- Existing Stage 1 parser tests remain valid.

#### Documentation updates

- Add taxonomy methodology doc.
- Add policy schema doc.
- Add read/pair evidence schema docs.
- Explain relationship to `jlanej/nonhuman-screen` as conceptual reference:
  - lineage-aware classification;
  - human-homology guard;
  - UniVec/synthetic handling;
  - preservation of Kraken evidence;
  - no direct code copying unless licensing and attribution are explicitly addressed.
- Explain distinction from CSC post-alignment contamination workflows.

#### Acceptance criteria

- `inspect-db` reports DB/taxonomy status and human lineage availability.
- `interpret` produces read/pair evidence tables from existing Kraken2 TSV and FASTQ.
- Missing taxonomy does not produce confident non-human removal labels.
- Human-lineage ancestors are not labeled non-human.
- Pair labels are mutually exclusive and reconciliation proves every pair accounted for once.
- Policy file and hash are recorded.

#### Dependencies on earlier PRs

Requires PR 1 for FASTQ validation, read-name normalization, schema/provenance foundations.

#### Major scientific or operational risks

- Kraken2 hitlist semantics can be misinterpreted.
- Taxonomy edge cases can create false non-human calls.
- Synthetic/vector representation varies by database.
- Quality metrics could be mistaken for classification confidence if docs are unclear.

#### Rollback or partial deployment

If interpretation logic needs revision, users can still rely on Stage 1 raw Kraken2 output and PR 1 validation. Evidence tables should be marked with schema and policy versions so outputs from experimental policies can be invalidated.

#### Repository capability after merge

The repository can inspect a Kraken2 database, interpret raw Kraken2 output in a lineage-aware way, and produce evidence-rich machine-readable read/pair tables without yet performing destructive filtering.

### 5.3 PR 3 — Policy-driven synchronized FASTQ binning and taxonomic summaries

#### Concise title

**Policy-driven synchronized FASTQ binning and taxonomic summaries**

#### Primary goal

Turn evidence tables into synchronized paired FASTQ output bins under explicit, recorded policies while preserving reviewability and count reconciliation.

#### Why it belongs at this stage

Once interpretation is available and tested, the next coherent capability is safe action: write paired FASTQs suitable for downstream alignment without losing evidence or splitting mates.

#### User-visible capabilities added

- New `bin-fastq` command.
- Top-level synchronized paired FASTQ bins:
  - human;
  - nonhuman;
  - uncertain;
  - discordant;
  - synthetic/vector.
- Manifest with counts and checksums/sizes.
- Taxonomic summaries by taxid, rank, lineage, and broad domain.
- Optional taxon-specific extraction command.
- Policy comparison/report mode.

#### Scope

Likely implementation modules:

- `kraken_read_parser/binning.py`
- `kraken_read_parser/outputs.py`
- `kraken_read_parser/summaries.py`
- possibly `kraken_read_parser/extract.py`

Specific work:

- Stream original R1/R2 FASTQ files and pair-evidence table together by normalized id.
- Write both mates to the same bin.
- Compress outputs with gzip.
- Generate output manifest:
  - bin file paths;
  - pair counts;
  - read counts;
  - base counts;
  - optional file sizes;
  - optional md5/sha256 if configured;
  - policy and schema versions.
- Default action mapping:
  - `human_consistent`, `unclassified`, `uncertain_low_evidence` → keep in human alignment output by default or, if producing mutually exclusive physical bins, document `human_plus_review` downstream mode;
  - `nonhuman_confident` → nonhuman bin;
  - `discordant_human_nonhuman` → discordant review bin;
  - `synthetic_vector` → synthetic/vector bin.
- To satisfy both mutually exclusive accounting and downstream usability, implement:
  - mutually exclusive physical bins; and
  - a manifest-defined “recommended human alignment input set.”
- Add `--mode` options:
  - `review-only`: write tables/summaries only;
  - `write-all-bins`: write all mutually exclusive bins;
  - `write-human-only`: write only the downstream human/kept FASTQs plus manifest.
- Add `extract-taxon` for user-selected taxid/lineage, not default per-taxid FASTQ proliferation.
- Add summaries:
  - `taxon_summary.tsv`;
  - `domain_summary.tsv`;
  - `reason_code_summary.tsv`;
  - `policy_action_summary.tsv`.

#### Explicit out-of-scope items

- Nextflow/SLURM orchestration.
- Running BWA/GATK.
- Empirical threshold tuning.
- Automatic variant artifact assessment.

#### Important compatibility considerations

- Do not change Stage 1 `run-kraken`.
- Evidence table schema from PR 2 is the input contract.
- FASTQ outputs must preserve original read headers and sequences/qualities exactly.
- Output bins must be reproducible from the same evidence and policy.
- The user should be able to rerun binning with a new policy without rerunning Kraken2.

#### Major repository areas likely to be affected

- New binning/output modules.
- CLI.
- `.gitignore`.
- README.
- Docs for output contract and downstream integration.
- Tests with golden FASTQ outputs.

#### Required unit, integration, functional, and regression tests

Unit tests:

- Action mapping from pair labels to bins.
- Both mates always written to same bin.
- Gzip output writing.
- Manifest count generation.
- Taxon summary aggregation.
- Taxon extraction by exact taxid.
- Taxon extraction by descendant lineage.
- Policy comparison identifies action changes.

Integration tests:

- Synthetic five-pair fixture covering all labels produces:
  - correct mutually exclusive bins;
  - exact expected record counts;
  - original headers preserved;
  - no sequence/quality changes.
- Reconciliation:
  - input pairs = sum of all output-bin pairs;
  - no duplicate output pair ids;
  - no missing pairs.

Functional tests:

- `bin-fastq` runs from synthetic evidence table and paired FASTQs.
- `extract-taxon` creates only requested taxon FASTQ pair.
- Downstream human FASTQ contract documented and testable.

Regression tests:

- Existing Stage 1/PR 1/PR 2 commands continue working.

#### Documentation updates

- Add “Output contract for downstream aligners and variant callers.”
- Document bin definitions and default action policy.
- Document how to recover candidate non-human reads by taxon.
- Document why default behavior avoids unbounded per-taxid FASTQ files.
- Add example commands for:
  - interpret only;
  - write all bins;
  - generate human alignment FASTQs;
  - extract cervid/ruminant/artiodactyl candidate pairs.

#### Acceptance criteria

- Physical bin outputs are synchronized paired FASTQ files.
- Every input pair is accounted for exactly once in mutually exclusive bins.
- The manifest records counts by bin and policy.
- No default creates per-taxid FASTQ explosion.
- A user can generate taxon-specific FASTQs on demand.
- Human alignment output contract is explicit.

#### Dependencies on earlier PRs

Requires PR 1 and PR 2.

#### Major scientific or operational risks

- Users may misunderstand whether `uncertain`/`discordant` are included in downstream human FASTQs.
- Binning from large evidence tables may become I/O-bound.
- Reconciliation failures must be strict to avoid silent data loss.

#### Rollback or partial deployment

If binning has issues, evidence interpretation from PR 2 remains usable. Users can avoid `bin-fastq` and inspect tables/summaries only.

#### Repository capability after merge

The repository can run a complete local FASTQ-first evidence-and-binning workflow from paired FASTQ + Kraken2 output to synchronized human/non-human/review FASTQ bins and audit manifests.

### 5.4 PR 4 — Workflow, reproducibility, proof-of-concept, and downstream integration readiness

#### Concise title

**Workflow, reproducibility, proof-of-concept, and downstream integration readiness**

#### Primary goal

Add production-facing workflow scaffolding, container guidance, CI hardening, proof-of-concept documentation, and downstream SNV/indel integration contracts without coupling the core CLI to any one HPC environment.

#### Why it belongs at this stage

Workflow orchestration should not drive core scientific logic. It should wrap stable CLI commands after validation, interpretation, and binning are implemented.

#### User-visible capabilities added

- Apptainer-compatible container definition or documented build path.
- Nextflow workflow for validate → run Kraken2 → inspect DB → interpret → bin.
- SLURM profile/example config without institution-specific paths.
- Resumable workflow stages.
- Resource guidance per stage.
- External-data proof-of-concept protocol.
- Downstream SNV/indel caller integration instructions.
- CI workflow for unit tests and lint/type checks if adopted.
- Optional real-Kraken2/database integration test hook gated by environment variables.

#### Scope

Likely repository areas:

- `workflows/nextflow/`
- `containers/`
- `docs/hpc.md`
- `docs/proof_of_concept.md`
- `docs/downstream_snv_indel.md`
- `.github/workflows/ci.yml`
- `examples/`
- `policies/`

Specific work:

- Add a Nextflow pipeline with independent processes:
  - `VALIDATE_FASTQ`
  - `RUN_KRAKEN`
  - `INSPECT_DB`
  - `INTERPRET`
  - `BIN_FASTQ`
  - `SUMMARIZE`
- Allow starting from existing Kraken2 TSV to avoid rerunning Kraken2.
- Add parameters for:
  - sample sheet;
  - R1/R2 paths;
  - database path;
  - policy file;
  - output directory;
  - threads/resources;
  - container image.
- Add local and SLURM profiles but avoid fixed accounts/partitions.
- Add Apptainer guidance:
  - either build from Docker/OCI image or use a definition file;
  - document external Kraken2 DB mount.
- Add CI:
  - Python 3.9+ matrix if feasible;
  - `pytest`;
  - optional formatting/linting if adopted in pyproject.
- Add proof-of-concept runbook using external miniCRAM-derived FASTQs:
  - no real data committed;
  - expected directory layout;
  - commands to run parser;
  - commands to pass unfiltered and filtered FASTQs to `fastq_snv-indel_caller`;
  - metrics to compare.
- Add downstream integration contract:
  - original unfiltered FASTQs and filtered human FASTQs must run through identical BWA/GATK settings;
  - sample/read identity preservation;
  - output manifest path recorded with downstream run.

#### Explicit out-of-scope items

- Implementing BWA/GATK/SV caller in this repository.
- Institutional SLURM account/partition defaults.
- Committing miniCRAMs, real FASTQs, Kraken DBs, or large outputs.
- Scientifically declaring threshold success before empirical review.
- Full WGS-scale validation, though the workflow should be designed for it.

#### Important compatibility considerations

- Core CLI must remain usable without Nextflow.
- Workflow should call public CLI commands rather than importing internal Python functions.
- Existing local commands should not require containers.
- Workflow should support reuse of raw Kraken2 output.

#### Major repository areas likely to be affected

- docs;
- workflow files;
- container files;
- CI files;
- example policies/sample sheets;
- `.gitignore`.

#### Required unit, integration, functional, and regression tests

Unit tests:

- No major new unit logic unless workflow helper scripts are added.

Integration tests:

- Nextflow syntax/config validation if Nextflow is available.
- Dry-run-like workflow test using mocked Kraken2 executable or prebuilt synthetic Kraken2 TSV.
- Container build smoke test if practical in CI; otherwise document manual test.

Functional tests:

- End-to-end synthetic workflow:
  - validate fixtures;
  - skip or mock Kraken2;
  - inspect fake DB;
  - interpret;
  - bin;
  - verify manifest.
- Optional real Kraken2 integration test gated by:
  - `KRAKEN_READ_PARSER_TEST_DB`;
  - `KRAKEN2_BIN`;
  - not run in default CI.

Regression tests:

- All prior test suites pass.
- CLI help output remains coherent.

#### Documentation updates

- HPC workflow guide.
- Apptainer guide.
- Sample sheet format.
- Resource estimates and tuning:
  - Kraken2 DB loading memory;
  - CPU threads;
  - output storage;
  - interpretation/binning I/O.
- Proof-of-concept guide for `BS_15AFEJE8` and `BS_CJ2YQ5XQ` external FASTQs.
- Downstream SNV/indel integration guide.
- Future SV integration placeholder.

#### Acceptance criteria

- Users can run the entire synthetic workflow locally without a real Kraken2 DB by using mocked or precomputed Kraken evidence.
- Users can run real Kraken2 by supplying a DB and binary.
- Workflow can resume from existing Kraken2 TSV.
- Docs clearly state that real human data, miniCRAMs, derived FASTQs, Kraken DBs, and HPC work dirs must remain outside Git.
- Downstream caller contract is documented and independent of the caller repository internals.

#### Dependencies on earlier PRs

Requires PRs 1–3.

#### Major scientific or operational risks

- Workflow complexity can obscure core CLI behavior.
- Containerized Kraken2/database handling can become environment-specific.
- Nextflow tests may be difficult in minimal CI environments.

#### Rollback or partial deployment

Workflow/docs can be rolled back without affecting the core Python CLI. If Nextflow support is unstable, keep container and proof-of-concept docs while marking workflow experimental.

#### Repository capability after merge

The repository can support local development, synthetic CI validation, external real-data proof-of-concept runs, and scalable HPC execution while keeping the core FASTQ-first parser independent from any one scheduler or downstream caller.

---

## 6. Cross-PR testing and validation strategy

### 6.1 Always-on tests

Run in default CI and local development:

```bash
python -m pytest -q
```

The reviewed baseline passed with 12 tests.

### 6.2 Test fixture strategy

Use only small synthetic or existing development FASTQs in Git. Do not commit:

- real human miniCRAMs;
- miniCRAM-derived FASTQs;
- real Kraken2 database;
- full Kraken2 outputs from real data;
- HPC working directories.

### 6.3 Synthetic taxonomy fixtures

Create tiny artificial taxonomy files under `tests/fixtures/taxonomy/` representing:

- root;
- cellular organisms;
- Eukaryota;
- Metazoa;
- Chordata;
- Mammalia;
- Primates;
- Hominidae;
- Homo;
- Homo sapiens taxid 9606;
- a non-human mammal lineage;
- Cervidae/Ruminantia/Artiodactyla-like test taxa;
- bacteria;
- virus;
- fungi;
- synthetic/vector taxid.

These are not biological truth sets; they are software fixtures to prove lineage logic.

### 6.4 Golden-output tests

For PR 3, use a tiny paired FASTQ plus synthetic evidence table and expected bin outputs. Tests should compare:

- record ids;
- sequences;
- qualities;
- bin counts;
- manifest counts;
- reconciliation totals.

### 6.5 Performance tests

Add non-default performance smoke tests that generate synthetic FASTQ/Kraken rows at larger scale but keep CI runtime bounded. Test streaming behavior by ensuring code iterates rather than materializing whole files where possible.

### 6.6 Reconciliation invariants

Every workflow stage should enforce:

```text
input_pairs = interpreted_pairs
input_pairs = sum(mutually_exclusive_output_bin_pairs)
no pair appears in more than one mutually exclusive bin
no mate is emitted without its partner
```

### 6.7 Error-mode tests

Explicitly test failures for:

- malformed FASTQ;
- truncated gzip;
- R1/R2 count mismatch;
- R1/R2 id mismatch;
- Kraken TSV malformed row;
- Kraken/FASTQ id mismatch;
- missing taxonomy;
- missing names;
- invalid policy;
- output overwrite without `--overwrite`.

---

## 7. Proof-of-concept experiment plan

### 7.1 Inputs

External, not committed:

- `BS_15AFEJE8`
  - source CRAM: `9ad09e99-6558-481f-adb2-58fcf0cc65d5.cram`
  - region: `chr17:75662000-75664000`
- `BS_CJ2YQ5XQ`
  - source CRAM: `70e9db4a-f442-4e47-8ec0-d0ef12b212e2.cram`
  - region: `chr12:6974000-6975000`

The miniCRAM-derived FASTQs are enriched for known artifacts and must not drive hard-coded logic.

### 7.2 Parser proof-of-concept steps

For each sample:

1. Convert miniCRAM to paired FASTQ externally.
2. Validate paired FASTQs with `validate-fastq`.
3. Run Kraken2 with the chosen database using `run-kraken`.
4. Inspect database/taxonomy with `inspect-db`.
5. Interpret evidence with the default sensitive policy.
6. Write all bins with `bin-fastq`.
7. Extract/highlight target hoofed-animal lineages:
   - Cervidae if represented;
   - Ruminantia;
   - Artiodactyla;
   - broader mammalian non-human lineages if needed.

### 7.3 Downstream SNV/indel comparison

For each sample, run identical downstream settings through `sashawin7/fastq_snv-indel_caller`:

```text
unfiltered FASTQ pair
→ BWA-MEM
→ coordinate-sorted BAM
→ GATK MarkDuplicates
→ GATK HaplotypeCaller in GVCF mode
```

and

```text
filtered human FASTQ pair
→ same BWA-MEM settings
→ same coordinate-sort settings
→ same GATK MarkDuplicates settings
→ same HaplotypeCaller settings
```

### 7.4 Metrics to collect

#### Parser metrics

- total input pairs;
- pairs per label/action;
- candidate non-human pairs;
- discordant pairs;
- uncertain pairs;
- synthetic/vector pairs;
- taxon/domain summaries;
- target hoofed-animal lineage counts;
- quality summaries for removed versus retained pairs;
- local count reconciliation.

#### Variant metrics

- candidate false-positive variant presence/absence;
- alternate-supporting read count before/after;
- total local depth before/after;
- reference-supporting depth before/after;
- allele balance before/after;
- whether removed reads disproportionately support false ALT calls;
- whether true-looking human coverage remains sufficient.

### 7.5 Interpretation cautions

- These regions are enriched for known artifacts and not representative WGS.
- Success means “promising evidence for further validation,” not a final threshold.
- If filtering removes local coverage broadly, the policy is too aggressive.
- If the suspected deer/hoofed signal appears, it should be reported as taxonomic evidence, not assumed sample identity.

---

## 8. HPC and downstream integration plan

### 8.1 Core principle

The Python CLI remains the authoritative implementation. Nextflow/SLURM/Apptainer wrap CLI commands but do not contain independent scientific logic.

### 8.2 Workflow stages

1. **FASTQ validation**
   - CPU: low
   - memory: low
   - I/O: reads full FASTQ pair
   - resumable: yes
2. **Kraken2 classification**
   - CPU: configurable threads
   - memory: database-dependent, often high
   - I/O: reads FASTQs, writes large Kraken TSV/report
   - resumable: yes via existing output checks
   - expensive stage to avoid repeating
3. **Database inspection**
   - CPU/memory: low-to-moderate depending taxonomy size
   - resumable: yes
4. **Interpretation**
   - CPU: moderate
   - memory: bounded/streaming where possible
   - I/O: Kraken TSV + FASTQ + taxonomy → evidence tables
   - cheaper than Kraken2
5. **Binning**
   - CPU: low
   - I/O: reads FASTQ + evidence, writes compressed FASTQs
   - rerunnable under new policies when evidence/action changes
6. **Summaries/extraction**
   - CPU/I/O: low-to-moderate
   - rerunnable

### 8.3 Avoid repeated database loading

- Workflow should support starting from existing `SAMPLE.kraken2.tsv`.
- Policy comparison and binning should never require Kraken2 reruns.
- Taxonomy parse caches can be added later but should not be required.

### 8.4 Apptainer

Recommended:

- Container includes Python package and Kraken2 binary where licensing permits.
- Kraken2 database remains an external mounted path.
- Policy files and sample sheets are mounted inputs.
- Outputs are written to mounted project/scratch paths.

### 8.5 Nextflow/SLURM

Recommended:

- Generic `slurm` profile with configurable executor options.
- No hard-coded account, partition, module, scratch, or institution path.
- Resource labels:
  - `low`
  - `medium`
  - `kraken_db`
  - `io_heavy`
- Sample sheet with:
  - `sample_id`
  - `r1`
  - `r2`
  - optional `existing_kraken2_tsv`
  - optional `existing_report`

### 8.6 Downstream caller integration

The parser should provide a documented output contract, not import or call the other repository directly.

Contract:

- `human`/kept R1/R2 FASTQs are ordinary synchronized gzip FASTQs.
- Original read headers are preserved.
- Sample id is stable.
- Manifest records which policy produced the filtered FASTQs.
- Unfiltered and filtered FASTQs are both available for identical downstream execution.
- Non-human/discordant/uncertain bins remain available for review and recovery.

---

## 9. Risks, unresolved questions, and deferred work

### 9.1 Major scientific risks

1. **False non-human labels from shared homology.** Human-like k-mers in viral, mammalian, or repetitive references can create misleading assignments. The human-homology guard and uncertain labels reduce but do not eliminate this risk.
2. **Database composition drives results.** A Kraken2 database lacking relevant cervid/ruminant/artiodactyl references may miss the suspected signal. A database with contaminated or poorly labeled assemblies may create false signal.
3. **MiniCRAM-derived FASTQs are biased.** They are useful for proof of concept but cannot set production thresholds alone.
4. **Removing reads can reduce coverage.** Artifact reduction must be evaluated against coverage preservation.
5. **Taxonomy versions change.** Taxid lineage and names can shift, so database/taxonomy provenance is essential.

### 9.2 Operational risks

1. **WGS output size.** Evidence tables and binned FASTQs can be large.
2. **File-handle explosion.** Avoided by not writing per-taxid FASTQs by default.
3. **Gzip I/O bottlenecks.** May require compression-level tuning or pigz support later.
4. **Workflow portability.** Nextflow profiles must stay generic.
5. **Schema churn.** Early schema discipline is needed.

### 9.3 Questions for project owner/domain expert

1. Which Kraken2 database should be the first recommended validation database?
2. Should Kraken2 `--confidence` remain unset for evidence sensitivity, or should a conservative nonzero value be configurable in `run-kraken`?
3. What is the minimum acceptable local coverage preservation criterion in proof-of-concept regions?
4. Should discordant pairs be included in default human alignment output during proof of concept or kept only in review bins?
5. Which synthetic/vector taxids should be recognized for the selected database beyond UniVec-Core-like entries?
6. What broad taxonomic categories matter most for reporting in human WGS/WES contamination contexts?
7. What downstream SV caller output contract will be needed later?

### 9.4 Deferred work

- Variant-aware filtering.
- Automatic threshold optimization.
- Cohort-level contamination modeling.
- SV-caller integration.
- Native Parquet/Arrow outputs.
- Database download/build automation.
- Web dashboards.
- General metagenomics use cases.
- RNA-seq/amplicon/metatranscriptomics support.

---

## 10. Definition of done for the entire update

The next major phase is complete when the repository can demonstrably do all of the following:

1. Accept paired-end human genomic FASTQ inputs without requiring BAM/CRAM, genomic coordinates, or variant calls.
2. Validate FASTQ integrity for gzip and uncompressed inputs, including malformed/truncated records, mate synchronization, read-name normalization, empty inputs, and count mismatches.
3. Run Kraken2 in paired mode while preserving raw per-read Kraken2 output, report, stderr, and rich provenance, maintaining Stage 1 compatibility.
4. Inspect a Kraken2 database and taxonomy, including human lineage availability, broad domain support, synthetic/vector representation, and database provenance.
5. Interpret raw Kraken2 output into lineage-aware read-level and pair-level evidence tables without assuming “not exactly 9606” means non-human.
6. Preserve raw and derived evidence sufficient to rerun interpretation and binning under new thresholds without rerunning Kraken2 when possible.
7. Use explicit, versioned, configurable policies with policy hashes recorded in outputs.
8. Distinguish at least:
   - human-consistent pairs;
   - confident non-human pairs;
   - uncertain/low-evidence pairs;
   - discordant human/non-human pairs;
   - unclassified pairs;
   - synthetic/vector-like pairs.
9. Keep paired reads synchronized and never place R1 and R2 into different final action bins.
10. Produce synchronized gzip FASTQ bins suitable for downstream aligners and variant callers.
11. Avoid uncontrolled per-taxid FASTQ proliferation by using evidence tables and summaries as the primary taxonomic organization, with on-demand taxon extraction.
12. Produce reconciliation reports proving every input pair is accounted for exactly once in mutually exclusive outputs.
13. Provide a clear downstream SNV/indel integration path that compares unfiltered and filtered FASTQs under identical alignment/calling settings.
14. Provide an HPC workflow wrapper that is resumable, Apptainer-compatible, Nextflow/SLURM-ready, and independent of institution-specific paths.
15. Document proof-of-concept execution for the two external miniCRAM-derived sample FASTQs without committing real human data.
16. Pass all default tests without requiring a real Kraken2 database.

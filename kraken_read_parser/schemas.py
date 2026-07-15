"""Machine-readable artifact schema declarations."""
from __future__ import annotations

FASTQ_VALIDATION_SCHEMA = {"schema_name": "kraken_read_parser.fastq_validation", "schema_version": 1}
RUN_METADATA_SCHEMA = {"schema_name": "kraken_read_parser.run_metadata", "schema_version": 1}
READ_EVIDENCE_SCHEMA = {"schema_name": "kraken_read_parser.read_evidence", "schema_version": 1}
PAIR_EVIDENCE_SCHEMA = {"schema_name": "kraken_read_parser.pair_evidence", "schema_version": 1}
BINNING_MANIFEST_SCHEMA = {"schema_name": "kraken_read_parser.binning_manifest", "schema_version": 1}

DECLARED_SCHEMAS = {
    item["schema_name"]: item["schema_version"]
    for item in [
        FASTQ_VALIDATION_SCHEMA,
        RUN_METADATA_SCHEMA,
        READ_EVIDENCE_SCHEMA,
        PAIR_EVIDENCE_SCHEMA,
        BINNING_MANIFEST_SCHEMA,
    ]
}

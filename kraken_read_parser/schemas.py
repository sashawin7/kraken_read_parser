"""Machine-readable artifact schema declarations."""
FASTQ_VALIDATION_SCHEMA={'schema_name':'kraken_read_parser.fastq_validation','schema_version':1}
RUN_METADATA_SCHEMA={'schema_name':'kraken_read_parser.run_metadata','schema_version':1}
DATABASE_PROVENANCE_SCHEMA={'schema_name':'kraken_read_parser.database_provenance','schema_version':1}
KRAKEN_SUMMARY_SCHEMA={'schema_name':'kraken_read_parser.kraken_summary','schema_version':1}
DECLARED_SCHEMAS={x['schema_name']:x['schema_version'] for x in (FASTQ_VALIDATION_SCHEMA,RUN_METADATA_SCHEMA,DATABASE_PROVENANCE_SCHEMA,KRAKEN_SUMMARY_SCHEMA)}

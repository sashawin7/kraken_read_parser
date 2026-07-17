from pathlib import Path
import pytest
from kraken_read_parser.report import parse_report, derive_standard_report, ReportParseError

def test_enriched_report_and_compatibility(tmp_path):
    src=tmp_path/'enriched.tsv'; dst=tmp_path/'standard.tsv'
    src.write_text('100.00\t10\t2\tR\t1\t20\t5\t  root\n')
    row=next(parse_report(src)); assert row.name=='root' and row.minimizers==20 and row.distinct_minimizers==5
    derive_standard_report(src,dst)
    assert dst.read_text()=='100.00\t10\t2\tR\t1\t  root\n'

def test_mixed_report_shape_is_line_numbered(tmp_path):
    p=tmp_path/'r';p.write_text('1\t1\t1\tR\t1\troot\n1\t1\t1\tR\t1\t1\t1\troot\n')
    with pytest.raises(ReportParseError,match=':2: inconsistent'): list(parse_report(p))

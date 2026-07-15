import gzip
import json
from pathlib import Path

import pytest

from kraken_read_parser.fastq import FastqValidationError, normalize_read_name, validate_paired_fastq
from kraken_read_parser.cli import main


def write_fastq(path: Path, records):
    text = "".join(f"@{h}\n{s}\n+\n{q}\n" for h, s, q in records)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(text)
    else:
        path.write_text(text, encoding="utf-8")


def assert_fails(tmp_path, r1_records, r2_records, match):
    r1 = tmp_path / "r1.fastq"
    r2 = tmp_path / "r2.fastq"
    if isinstance(r1_records, str):
        r1.write_text(r1_records, encoding="utf-8")
    else:
        write_fastq(r1, r1_records)
    if isinstance(r2_records, str):
        r2.write_text(r2_records, encoding="utf-8")
    else:
        write_fastq(r2, r2_records)
    with pytest.raises(FastqValidationError, match=match):
        validate_paired_fastq(r1=r1, r2=r2, sample_id="S", outdir=tmp_path / "out")


def test_validate_plain_fastq_counts_and_schema(tmp_path):
    r1 = tmp_path / "r1.fastq"
    r2 = tmp_path / "r2.fastq"
    write_fastq(r1, [("read1/1", "ACGT", "IIII"), ("read2/1", "AA", "##")])
    write_fastq(r2, [("read1/2", "TGCA", "JJJJ"), ("read2/2", "TT", "!!")])
    result = validate_paired_fastq(r1=r1, r2=r2, sample_id="S", outdir=tmp_path / "out")
    assert result["schema_name"] == "kraken_read_parser.fastq_validation"
    assert result["schema_version"] == 1
    assert result["validation_status"] == "passed"
    assert result["pairs"]["records"] == 2
    assert result["files"]["r1"]["sequence_bases"] == 6
    saved = json.loads(Path(result["output_file"]).read_text())
    assert saved["inputs"]["r1"]["size_bytes"] > 0


def test_validate_gzip_fastq(tmp_path):
    r1 = tmp_path / "r1.fastq.gz"
    r2 = tmp_path / "r2.fastq.gz"
    write_fastq(r1, [("INST:1:FC:1:1:1:1 1:N:0:ACGT", "AC", "II")])
    write_fastq(r2, [("INST:1:FC:1:1:1:1 2:N:0:ACGT", "GT", "II")])
    assert validate_paired_fastq(r1=r1, r2=r2, sample_id="GZ", outdir=tmp_path / "out")["pairs"]["records"] == 1


@pytest.mark.parametrize(
    "r1,r2,match",
    [
        ("", "", "empty"),
        ("@r1\nAC\n+\n", [("r1", "AC", "II")], "incomplete"),
        ("r1\nAC\n+\nII\n", [("r1", "AC", "II")], "header"),
        ("@r1\nAC\n-\nII\n", [("r1", "AC", "II")], "separator"),
        ("@r1\nAC\n+\nI\n", [("r1", "AC", "II")], "sequence length"),
        ([("r1", "AC", "II"), ("r2", "AC", "II")], [("r1", "AC", "II")], "count mismatch"),
        ([("r1", "AC", "II")], [("r2", "AC", "II")], "identifiers do not match"),
    ],
)
def test_invalid_fastq_modes(tmp_path, r1, r2, match):
    assert_fails(tmp_path, r1, r2, match)


def test_corrupt_gzip_reports_read_failure(tmp_path):
    r1 = tmp_path / "r1.fastq.gz"
    r2 = tmp_path / "r2.fastq.gz"
    r1.write_bytes(b"not gzip")
    write_fastq(r2, [("r1", "AC", "II")])
    with pytest.raises(FastqValidationError, match="failed to read"):
        validate_paired_fastq(r1=r1, r2=r2, sample_id="BAD", outdir=tmp_path / "out")


def test_read_name_normalization_supported_and_conservative():
    assert normalize_read_name("@read/1") == normalize_read_name("@read/2") == "read"
    assert normalize_read_name("@A:B 1:N:0:TAG") == normalize_read_name("@A:B 2:N:0:TAG") == "A:B"
    assert normalize_read_name("@same") == normalize_read_name("@same") == "same"
    assert normalize_read_name("@sample/10") != normalize_read_name("@sample/20")
    assert normalize_read_name("@abc 9:weird") == "abc 9:weird"


def test_cli_validate_success_and_failure(tmp_path, capsys):
    r1 = tmp_path / "r1.fastq"
    r2 = tmp_path / "r2.fastq"
    write_fastq(r1, [("read/1", "AC", "II")])
    write_fastq(r2, [("read/2", "GT", "II")])
    assert main(["validate-fastq", "--r1", str(r1), "--r2", str(r2), "--sample-id", "CLI", "--outdir", str(tmp_path / "out")]) == 0
    assert "passed" in capsys.readouterr().out
    assert main(["validate-fastq", "--r1", str(tmp_path / "missing.fastq"), "--r2", str(r2), "--sample-id", "CLI2", "--outdir", str(tmp_path / "out2")]) == 1
    assert "ERROR:" in capsys.readouterr().err

import pytest
from kraken_read_parser.parser import KrakenParserError, parse_kraken2, parse_line
from kraken_read_parser.kraken import sanity_check_output


def test_valid_paired_record():
    rec = parse_line("C\tread1\t9606\t100|101\t9606:10 |:| 9606:11\n")
    assert rec.status == "C"
    assert rec.length_r1 == 100
    assert rec.length_r2 == 101
    assert rec.hitlist_r2 == " 9606:11"
    assert rec.has_mate_separator


def test_malformed_strict_errors():
    with pytest.raises(KrakenParserError):
        parse_line("bad\trow\n", strict=True)


def test_malformed_non_strict_skips():
    rows = list(parse_kraken2(["bad\trow\n", "U\tr\t0\t10|10\t0:10 |:| 0:10\n"], strict=False))
    assert len(rows) == 1


def test_absent_mate_separator_record():
    rec = parse_line("U\tr\t0\t10\t0:10\n")
    assert rec.hitlist_r2 is None
    assert not rec.has_mate_separator


def test_sanity_check_rejects_unpaired(tmp_path):
    p = tmp_path / "x.tsv"
    p.write_text("U\tr\t0\t10\t0:10\n")
    with pytest.raises(ValueError, match="paired output"):
        sanity_check_output(p)

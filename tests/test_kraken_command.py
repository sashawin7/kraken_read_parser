import json
import subprocess
from pathlib import Path

import pytest

from kraken_read_parser.kraken import build_kraken2_command, planned_outputs, run_kraken2


def touch_inputs(tmp_path):
    r1 = tmp_path / "r1.fq"; r2 = tmp_path / "r2.fq"; db = tmp_path / "db"; out = tmp_path / "out"
    r1.write_text("@r/1\nA\n+\n!\n"); r2.write_text("@r/2\nA\n+\n!\n"); db.mkdir(); out.mkdir()
    [(db / n).write_text("x") for n in ("hash.k2d", "opts.k2d", "taxo.k2d")]
    exe = tmp_path / "kraken2"; exe.write_text("#!/bin/sh\nexit 0\n"); exe.chmod(0o755)
    return r1, r2, db, out, exe


def test_command_construction(tmp_path):
    outputs = planned_outputs(tmp_path, "s1")
    cmd = build_kraken2_command(kraken2_bin="kraken2", db=Path("db"), threads=4, outputs=outputs, r1=Path("r1"), r2=Path("r2"))
    assert cmd == ["kraken2", "--paired", "--db", "db", "--threads", "4", "--output", str(outputs.output_tsv), "--report", str(outputs.report_tsv), "r1", "r2"]
    assert "--classified-out" not in cmd
    assert "--confidence" not in cmd
    assert "--memory-mapping" not in cmd


def test_command_construction_with_memory_mapping(tmp_path):
    outputs = planned_outputs(tmp_path, "s1")
    cmd = build_kraken2_command(
        kraken2_bin="kraken2", db=Path("db"), threads=4, outputs=outputs, r1=Path("r1"), r2=Path("r2"), memory_mapping=True
    )
    assert cmd.count("--memory-mapping") == 1
    assert cmd[-3:] == ["--memory-mapping", "r1", "r2"]


def test_overwrite_protection(tmp_path):
    r1, r2, db, out, exe = touch_inputs(tmp_path)
    (out / "sample.kraken2.tsv").write_text("exists")
    with pytest.raises(FileExistsError):
        run_kraken2(r1=r1, r2=r2, db=db, sample_id="sample", outdir=out, threads=1, kraken2_bin=str(exe))


def test_dry_run(tmp_path):
    r1, r2, db, out, exe = touch_inputs(tmp_path)
    md = run_kraken2(r1=r1, r2=r2, db=db, sample_id="sample", outdir=out, threads=2, kraken2_bin=str(exe), dry_run=True)
    assert md["dry_run"] is True
    assert md["exit_code"] is None
    assert md["memory_mapping"] is False
    assert not (out / "sample.run_metadata.json").exists()


def test_successful_mocked_run_writes_metadata(monkeypatch, tmp_path):
    r1, r2, db, out, exe = touch_inputs(tmp_path)
    def fake_run(cmd, stdout, stderr, text):
        (out / "sample.kraken2.tsv").write_text("C\tread1\t9606\t10|10\t9606:1 |:| 9606:1\n")
        (out / "sample.kraken2.report.tsv").write_text("100.00\t1\t0\tU\t0\tunclassified\n100.00\t1\t1\tR\t1\troot\n")
        stderr.write("ok\n")
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(subprocess, "run", fake_run)
    md = run_kraken2(r1=r1, r2=r2, db=db, sample_id="sample", outdir=out, threads=1, kraken2_bin=str(exe))
    saved = json.loads((out / "sample.run_metadata.json").read_text())
    assert md["exit_code"] == 0
    assert saved["sample_id"] == "sample"
    assert saved["command"][0] == str(exe)
    assert saved["memory_mapping"] is False


def test_memory_mapping_metadata_and_command_provenance(monkeypatch, tmp_path):
    r1, r2, db, out, exe = touch_inputs(tmp_path)

    def fake_run(cmd, stdout, stderr, text):
        (out / "sample.kraken2.tsv").write_text("C\tread1\t9606\t10|10\t9606:1 |:| 9606:1\n")
        (out / "sample.kraken2.report.tsv").write_text("100.00\t1\t0\tU\t0\tunclassified\n100.00\t1\t1\tR\t1\troot\n")
        stderr.write("ok\n")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    md = run_kraken2(r1=r1, r2=r2, db=db, sample_id="sample", outdir=out, threads=1, kraken2_bin=str(exe), memory_mapping=True)
    saved = json.loads((out / "sample.run_metadata.json").read_text())
    assert md["memory_mapping"] is True
    assert saved["memory_mapping"] is True
    assert md["command"].count("--memory-mapping") == 1
    assert saved["command"].count("--memory-mapping") == 1


def test_failed_mocked_run(monkeypatch, tmp_path):
    r1, r2, db, out, exe = touch_inputs(tmp_path)
    def fake_run(cmd, stdout, stderr, text):
        stderr.write("boom\n")
        return subprocess.CompletedProcess(cmd, 2)
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="exit code 2"):
        run_kraken2(r1=r1, r2=r2, db=db, sample_id="sample", outdir=out, threads=1, kraken2_bin=str(exe))
    assert (out / "sample.run_metadata.json").exists()

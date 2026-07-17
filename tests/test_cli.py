from kraken_read_parser.cli import build_parser, main


def test_cli_argument_parsing():
    args = build_parser().parse_args(["run-kraken", "--r1", "a", "--r2", "b", "--db", "db", "--sample-id", "s", "--outdir", "out", "--threads", "4"])
    assert args.command == "run-kraken"
    assert args.threads == 4
    assert args.kraken2_bin == "kraken2"
    assert args.memory_mapping is False


def test_cli_argument_parsing_memory_mapping_enabled():
    args = build_parser().parse_args([
        "run-kraken", "--r1", "a", "--r2", "b", "--db", "db", "--sample-id", "s", "--outdir", "out",
        "--threads", "4", "--memory-mapping",
    ])
    assert args.memory_mapping is True


def test_cli_dry_run(monkeypatch, tmp_path, capsys):
    r1 = tmp_path / "r1.fq"; r2 = tmp_path / "r2.fq"; db = tmp_path / "db"; out = tmp_path / "out"; exe = tmp_path / "kraken2"
    r1.write_text("x"); r2.write_text("x"); db.mkdir(); [(db / n).write_text("x") for n in ("hash.k2d", "opts.k2d", "taxo.k2d")]; exe.write_text("#!/bin/sh\n"); exe.chmod(0o755)
    code = main(["run-kraken", "--r1", str(r1), "--r2", str(r2), "--db", str(db), "--sample-id", "s", "--outdir", str(out), "--threads", "1", "--kraken2-bin", str(exe), "--dry-run"])
    assert code == 0
    assert "Kraken2 command" in capsys.readouterr().out


def test_cli_dry_run_memory_mapping_in_command(tmp_path, capsys):
    r1 = tmp_path / "r1.fq"; r2 = tmp_path / "r2.fq"; db = tmp_path / "db"; out = tmp_path / "out"; exe = tmp_path / "kraken2"
    r1.write_text("x"); r2.write_text("x"); db.mkdir(); [(db / n).write_text("x") for n in ("hash.k2d", "opts.k2d", "taxo.k2d")]; exe.write_text("#!/bin/sh\n"); exe.chmod(0o755)
    code = main([
        "run-kraken", "--r1", str(r1), "--r2", str(r2), "--db", str(db), "--sample-id", "s",
        "--outdir", str(out), "--threads", "1", "--kraken2-bin", str(exe), "--dry-run", "--memory-mapping",
    ])
    assert code == 0
    assert "--memory-mapping" in capsys.readouterr().out

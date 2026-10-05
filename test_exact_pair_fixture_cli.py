from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import cli_map_editor as editor


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_fixture(path: Path, target_id: str, bin_data: bytes, xdf_data: bytes) -> Path:
    fixture = {
        "schema": "kingai.exact-pair-fixture-set.v1",
        "fixture_count": 1,
        "fixtures": [
            {
                "schema": "kingai.exact-bin-xdf-fixture.v1",
                "target_id": target_id,
                "family": "synthetic",
                "software": "TEST",
                "bin": {
                    "sha256": sha(bin_data),
                    "size": len(bin_data),
                    "basename": "stock.bin",
                },
                "xdf": {
                    "sha256": sha(xdf_data),
                    "basename": "definition.xdf",
                },
            }
        ],
    }
    path.write_text(json.dumps(fixture), encoding="utf-8")
    return path


def test_load_exact_pair_fixture_selects_one_target(tmp_path):
    b = b"\x00" * 16
    x = b"<XDFFORMAT/>"
    p = make_fixture(tmp_path / "fixture.json", "ms42_0110ad", b, x)
    result = editor._load_exact_pair_fixture(p, "ms42_0110ad")
    assert result["target_id"] == "ms42_0110ad"
    assert result["bin"]["size"] == 16


def test_fixture_unknown_target_fails(tmp_path):
    b = b"\x00" * 16
    x = b"<XDFFORMAT/>"
    p = make_fixture(tmp_path / "fixture.json", "known", b, x)
    try:
        editor._load_exact_pair_fixture(p, "missing")
    except ValueError as exc:
        assert "matched 0 fixture" in str(exc)
    else:
        raise AssertionError("missing target must fail")


def test_hash_mismatch_stops_before_preflight(tmp_path, monkeypatch, capsys):
    bin_path = tmp_path / "stock.bin"
    xdf_path = tmp_path / "definition.xdf"
    bin_path.write_bytes(b"A" * 16)
    xdf_path.write_bytes(b"<XDFFORMAT/>")
    fixture = make_fixture(
        tmp_path / "fixture.json",
        "target",
        b"B" * 16,
        xdf_path.read_bytes(),
    )
    monkeypatch.setattr(
        editor,
        "cmd_preflight",
        lambda _args: (_ for _ in ()).throw(AssertionError("preflight must not run")),
    )
    args = SimpleNamespace(
        fixture=str(fixture),
        target_id="target",
        xdf=str(xdf_path),
        bin=str(bin_path),
    )
    assert editor.cmd_validate_fixture(args) == 1
    out = capsys.readouterr().out
    assert "BIN SHA-256 mismatch" in out
    assert "Preflight was NOT run" in out


def test_exact_match_delegates_to_existing_preflight(tmp_path, monkeypatch, capsys):
    bin_path = tmp_path / "stock.bin"
    xdf_path = tmp_path / "definition.xdf"
    bin_path.write_bytes(b"A" * 16)
    xdf_path.write_bytes(b"<XDFFORMAT/>")
    fixture = make_fixture(
        tmp_path / "fixture.json",
        "target",
        bin_path.read_bytes(),
        xdf_path.read_bytes(),
    )
    called = []

    def fake_preflight(args):
        called.append((args.xdf, args.bin))
        return 0

    monkeypatch.setattr(editor, "cmd_preflight", fake_preflight)
    args = SimpleNamespace(
        fixture=str(fixture),
        target_id="target",
        xdf=str(xdf_path),
        bin=str(bin_path),
    )
    assert editor.cmd_validate_fixture(args) == 0
    assert called == [(str(xdf_path), str(bin_path))]
    assert "Exact hashes and BIN size: MATCH" in capsys.readouterr().out


def test_fixture_validation_creates_no_files(tmp_path, monkeypatch):
    bin_path = tmp_path / "stock.bin"
    xdf_path = tmp_path / "definition.xdf"
    bin_path.write_bytes(b"A" * 16)
    xdf_path.write_bytes(b"<XDFFORMAT/>")
    fixture = make_fixture(
        tmp_path / "fixture.json",
        "target",
        bin_path.read_bytes(),
        xdf_path.read_bytes(),
    )
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(editor, "cmd_preflight", lambda _args: 0)
    args = SimpleNamespace(
        fixture=str(fixture),
        target_id="target",
        xdf=str(xdf_path),
        bin=str(bin_path),
    )
    assert editor.cmd_validate_fixture(args) == 0
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert before == after


def test_export_fixture_blocks_before_export_on_validation_failure(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(editor, "cmd_validate_fixture", lambda _args: 1)
    monkeypatch.setattr(editor, "cmd_export", lambda _args: calls.append("export") or 0)
    args = SimpleNamespace()
    assert editor.cmd_export_fixture(args) == 1
    assert calls == []


def test_export_fixture_reuses_existing_export_after_validation(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(editor, "cmd_validate_fixture", lambda _args: calls.append("validate") or 0)
    monkeypatch.setattr(editor, "cmd_export", lambda _args: calls.append("export") or 0)
    args = SimpleNamespace()
    assert editor.cmd_export_fixture(args) == 0
    assert calls == ["validate", "export"]

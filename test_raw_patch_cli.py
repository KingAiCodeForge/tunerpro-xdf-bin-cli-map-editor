"""Focused subprocess tests for raw-patch CLI commands."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parent
CLI = REPO / "cli_map_editor.py"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _case(tmp_path: Path):
    source = bytearray(range(64))
    source[40:46] = b"TST001"
    chunks = [
        {
            "name": "hook",
            "kind": "code",
            "offset": 4,
            "expected_hex": bytes(source[4:8]).hex().upper(),
            "replacement_hex": "A1A2A3A4",
        },
        {
            "name": "payload",
            "kind": "data",
            "offset": 20,
            "expected_hex": bytes(source[20:23]).hex().upper(),
            "replacement_hex": "B1B2B3",
        },
    ]
    patched = bytearray(source)
    patched[4:8] = bytes.fromhex(chunks[0]["replacement_hex"])
    patched[20:23] = bytes.fromhex(chunks[1]["replacement_hex"])
    manifest = {
        "schema": "kingai.raw-patch.v2",
        "patch_id": "synthetic-cli-roundtrip-v2",
        "address_space": "file_offset",
        "target": {
            "ecu": "Synthetic ECU",
            "software_id": "TST001",
            "image_layout": "64-byte full image fixture",
            "architecture": "synthetic-8",
            "parent_filename": "source.bin",
            "size": len(source),
            "base_sha256": _sha256(source),
            "patched_sha256": _sha256(patched),
            "identity_probes": [
                {
                    "name": "software-id",
                    "offset": 40,
                    "expected_hex": bytes(source[40:46]).hex().upper(),
                }
            ],
        },
        "chunks": chunks,
        "immutable_ranges": [
            {
                "name": "protected-vector",
                "offset": 32,
                "length": 8,
                "sha256": _sha256(source[32:40]),
            }
        ],
    }
    source_path = tmp_path / "source.bin"
    patched_path = tmp_path / "patched-input.bin"
    manifest_path = tmp_path / "patch.json"
    source_path.write_bytes(source)
    patched_path.write_bytes(patched)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return bytes(source), bytes(patched), source_path, patched_path, manifest_path


def _run(*args: object):
    return subprocess.run(
        [sys.executable, str(CLI), *(str(arg) for arg in args)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )


def _assert_common_report(stdout: str, direction: str, input_hash: str, output_hash: str):
    assert "Patch: synthetic-cli-roundtrip-v2" in stdout
    assert f"Direction: {direction}" in stdout
    assert f"Input SHA-256:  {input_hash}" in stdout
    assert f"Output SHA-256: {output_hash}" in stdout
    assert "Changed bytes: 7" in stdout
    assert "Expected bytes: MATCH" in stdout
    assert "Outside allowlist: 0" in stdout
    assert "Checksum: NOT_REQUESTED" in stdout
    assert re.search(r"Evidence SHA-256: [0-9A-F]{64}$", stdout, re.MULTILINE)


def test_verify_raw_patch_forward_is_read_only(tmp_path):
    source, patched, source_path, _patched_path, manifest_path = _case(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    completed = _run(
        "verify-raw-patch",
        "--bin",
        source_path,
        "--manifest",
        manifest_path,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    _assert_common_report(completed.stdout, "forward", _sha256(source), _sha256(patched))
    assert "Verification: PASS (no files written)" in completed.stdout
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == before


def test_verify_raw_patch_reverse_is_read_only(tmp_path):
    source, patched, _source_path, patched_path, manifest_path = _case(tmp_path)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    completed = _run(
        "verify-raw-patch",
        "--reverse",
        "--bin",
        patched_path,
        "--manifest",
        manifest_path,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    _assert_common_report(completed.stdout, "reverse", _sha256(patched), _sha256(source))
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == before


def test_apply_raw_patch_reports_checksum_and_evidence(tmp_path):
    _source, patched, source_path, _patched_path, manifest_path = _case(tmp_path)
    output_path = tmp_path / "applied.bin"

    completed = _run(
        "apply-raw-patch",
        "--bin",
        source_path,
        "--manifest",
        manifest_path,
        "--output",
        output_path,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert output_path.read_bytes() == patched
    assert "Checksum: NOT_REQUESTED" in completed.stdout
    evidence_match = re.search(
        r"Evidence SHA-256: ([0-9A-F]{64})$", completed.stdout, re.MULTILINE
    )
    assert evidence_match
    receipt_path = Path(str(output_path.resolve()) + ".receipt.json")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["evidence_sha256"] == evidence_match.group(1)


def test_real_ds2_manifest_verifies_through_trusted_cli_registry():
    workspace = REPO.parent
    case_dir = (
        workspace
        / "1bmw_ms42_tuning_guides"
        / "_ai_work"
        / "ms42_0110c6_ds2_logging_patch_20260920"
    )
    manifest_path = (
        case_dir
        / "ms42_0110c6_ds2_logging_feature_enhancement_strict_manifest_v2.json"
    )
    parent_path = (
        workspace
        / "1bmw_ms42_tuning_guides"
        / "all_ms42_bins"
        / "Siemens_MS42_0110C6_E46_M52TUB28_EU3_RHD (1).bin"
    )
    if not manifest_path.is_file() or not parent_path.is_file():
        pytest.skip("local MS42 DS2 integration fixtures are unavailable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "kingai.raw-patch.v2":
        pytest.skip("local MS42 DS2 manifest has not been upgraded to v2")

    completed = _run(
        "verify-raw-patch",
        "--bin",
        parent_path,
        "--manifest",
        manifest_path,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Direction: forward" in completed.stdout
    assert "Checksum: PASSED" in completed.stdout
    assert (
        "Output SHA-256: AF72CCEB84CF12D75A8791051A43BCE00F4CC33447ECF51C3B1B2625810ED9DD"
        in completed.stdout
    )
    assert "Verification: PASS (no files written)" in completed.stdout

"""Regression tests for strict exact-image raw patch manifests."""

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from raw_patch_manifest import (
    PatchManifestError,
    _prove_bounded_diff,
    _sha256,
    apply_patch_manifest,
    compute_evidence_sha256,
    load_patch_manifest,
    verify_patch_manifest,
)


def _case(tmp_path):
    source = bytearray(range(64))
    source[40:46] = b"TST001"
    chunks = [
        {
            "name": "hook",
            "kind": "code",
            "offset": "0x04",
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
        "patch_id": "synthetic-roundtrip-v2",
        "address_space": "file_offset",
        "target": {
            "ecu": "Synthetic ECU",
            "software_id": "TST001",
            "image_layout": "64-byte full image fixture",
            "architecture": "synthetic-8",
            "parent_filename": "source.bin",
            "size": len(source),
            "base_sha256": _sha256(bytes(source)),
            "patched_sha256": _sha256(bytes(patched)),
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
                "sha256": _sha256(bytes(source[32:40])),
            }
        ],
    }
    source_path = tmp_path / "source.bin"
    manifest_path = tmp_path / "patch.json"
    source_path.write_bytes(source)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return bytes(source), bytes(patched), manifest, source_path, manifest_path


def _write_manifest(path: Path, manifest):
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_forward_and_reverse_are_exact_hash_pinned_round_trip(tmp_path):
    source, patched, _manifest, source_path, manifest_path = _case(tmp_path)
    output = tmp_path / "patched.bin"

    receipt = apply_patch_manifest(source_path, manifest_path, output)

    assert source_path.read_bytes() == source
    assert output.read_bytes() == patched
    assert receipt["direction"] == "forward"
    assert receipt["proof"]["changed_bytes"] == 7
    assert receipt["proof"]["all_expected_bytes_matched"] is True
    assert receipt["proof"]["no_changes_outside_allowlist"] is True
    assert receipt["proof"]["result_sha256_matched"] is True
    assert Path(str(output) + ".receipt.json").exists()

    restored = tmp_path / "restored.bin"
    reverse_receipt = apply_patch_manifest(
        output, manifest_path, restored, reverse=True
    )
    assert restored.read_bytes() == source
    assert reverse_receipt["direction"] == "reverse"
    assert reverse_receipt["output"]["sha256"] == _sha256(source)


def test_identity_and_byte_gates_fail_without_writing_outputs(tmp_path):
    _source, _patched, original, source_path, _manifest_path = _case(tmp_path)
    mutations = []

    wrong_size = copy.deepcopy(original)
    wrong_size["target"]["size"] += 1
    mutations.append(wrong_size)

    wrong_hash = copy.deepcopy(original)
    wrong_hash["target"]["base_sha256"] = "00" * 32
    mutations.append(wrong_hash)

    wrong_identity = copy.deepcopy(original)
    wrong_identity["target"]["identity_probes"][0]["expected_hex"] = "424144303031"
    mutations.append(wrong_identity)

    wrong_bytes = copy.deepcopy(original)
    wrong_bytes["chunks"][0]["expected_hex"] = "00000000"
    mutations.append(wrong_bytes)

    wrong_result = copy.deepcopy(original)
    wrong_result["target"]["patched_sha256"] = "FF" * 32
    mutations.append(wrong_result)

    for index, manifest in enumerate(mutations):
        manifest_path = tmp_path / f"bad_{index}.json"
        output = tmp_path / f"bad_{index}.bin"
        _write_manifest(manifest_path, manifest)
        with pytest.raises(PatchManifestError):
            apply_patch_manifest(source_path, manifest_path, output)
        assert not output.exists()
        assert not Path(str(output) + ".receipt.json").exists()


@pytest.mark.parametrize("fault", ["overlap", "oob", "odd_hex", "duplicate", "unknown"])
def test_malformed_or_ambiguous_manifests_fail_closed(tmp_path, fault):
    _source, _patched, manifest, _source_path, _manifest_path = _case(tmp_path)
    manifest = copy.deepcopy(manifest)
    if fault == "overlap":
        manifest["chunks"][1]["offset"] = 6
    elif fault == "oob":
        manifest["chunks"][1]["offset"] = 63
    elif fault == "odd_hex":
        manifest["chunks"][0]["replacement_hex"] = "ABC"
    elif fault == "duplicate":
        manifest["chunks"][1]["name"] = manifest["chunks"][0]["name"]
    else:
        manifest["target"]["sha256"] = manifest["target"]["base_sha256"]
    path = tmp_path / f"{fault}.json"
    _write_manifest(path, manifest)
    with pytest.raises(PatchManifestError):
        load_patch_manifest(path)


def test_existing_paths_and_in_place_output_are_refused(tmp_path):
    _source, _patched, _manifest, source_path, manifest_path = _case(tmp_path)
    with pytest.raises(PatchManifestError, match="output must differ"):
        apply_patch_manifest(source_path, manifest_path, source_path)

    output = tmp_path / "exists.bin"
    output.write_bytes(b"do not replace")
    with pytest.raises(PatchManifestError, match="overwrite existing output"):
        apply_patch_manifest(source_path, manifest_path, output)
    assert output.read_bytes() == b"do not replace"

    output2 = tmp_path / "new.bin"
    receipt = Path(str(output2) + ".receipt.json")
    receipt.write_text("do not replace", encoding="utf-8")
    with pytest.raises(PatchManifestError, match="overwrite existing receipt"):
        apply_patch_manifest(source_path, manifest_path, output2)
    assert not output2.exists()
    assert receipt.read_text(encoding="utf-8") == "do not replace"


def test_bounded_diff_proof_rejects_extra_byte_outside_allowlist():
    source = bytes(range(16))
    result = bytearray(source)
    result[2] ^= 1
    result[12] ^= 1
    with pytest.raises(PatchManifestError, match="unexpected changes"):
        _prove_bounded_diff(source, bytes(result), [(2, 3)], {2})


def test_cli_apply_raw_patch_smoke(tmp_path):
    _source, patched, _manifest, source_path, manifest_path = _case(tmp_path)
    output = tmp_path / "cli-patched.bin"
    cli = Path(__file__).with_name("cli_map_editor.py")
    completed = subprocess.run(
        [
            sys.executable,
            str(cli),
            "apply-raw-patch",
            "--bin",
            str(source_path),
            "--manifest",
            str(manifest_path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert output.read_bytes() == patched
    assert "Outside allowlist: 0" in completed.stdout


def test_v1_manifest_is_rejected_with_rebuild_instruction(tmp_path):
    _source, _patched, manifest, _source_path, manifest_path = _case(tmp_path)
    manifest["schema"] = "kingai.raw-patch.v1"
    _write_manifest(manifest_path, manifest)

    with pytest.raises(PatchManifestError, match="rebuild it as v2"):
        load_patch_manifest(manifest_path)


@pytest.mark.parametrize(
    "field",
    ["ecu", "software_id", "image_layout", "architecture", "parent_filename"],
)
def test_semantic_target_metadata_is_required(tmp_path, field):
    _source, _patched, manifest, _source_path, manifest_path = _case(tmp_path)
    del manifest["target"][field]
    _write_manifest(manifest_path, manifest)

    with pytest.raises(PatchManifestError, match=f"target.{field}"):
        load_patch_manifest(manifest_path)


def test_identity_probes_are_binary_and_cannot_overlap_writes(tmp_path):
    _source, _patched, manifest, _source_path, manifest_path = _case(tmp_path)
    manifest["target"]["identity_probes"] = [
        {"name": "binary-id", "offset": 4, "expected_hex": "04050607"}
    ]
    _write_manifest(manifest_path, manifest)

    with pytest.raises(PatchManifestError, match="identity probe.*overlaps.*chunk"):
        load_patch_manifest(manifest_path)


def test_parent_filename_is_enforced_for_forward_input(tmp_path):
    source, _patched, _manifest, _source_path, manifest_path = _case(tmp_path)
    renamed = tmp_path / "renamed-parent.bin"
    renamed.write_bytes(source)

    with pytest.raises(PatchManifestError, match="input parent filename mismatch"):
        verify_patch_manifest(renamed, manifest_path)


def test_immutable_ranges_are_explicit_disjoint_and_hash_checked(tmp_path):
    _source, _patched, manifest, source_path, manifest_path = _case(tmp_path)

    overlapping = copy.deepcopy(manifest)
    overlapping["immutable_ranges"][0]["offset"] = 4
    overlapping["immutable_ranges"][0]["length"] = 4
    path = tmp_path / "overlap-immutable.json"
    _write_manifest(path, overlapping)
    with pytest.raises(PatchManifestError, match="immutable range.*overlaps.*chunk"):
        load_patch_manifest(path)

    wrong_hash = copy.deepcopy(manifest)
    wrong_hash["immutable_ranges"][0]["sha256"] = "00" * 32
    _write_manifest(manifest_path, wrong_hash)
    with pytest.raises(PatchManifestError, match="immutable range.*SHA-256 mismatch"):
        verify_patch_manifest(source_path, manifest_path)


def test_verify_only_writes_nothing_and_matches_apply_evidence(tmp_path):
    _source, patched, _manifest, source_path, manifest_path = _case(tmp_path)
    before = {path.name for path in tmp_path.iterdir()}

    verification = verify_patch_manifest(source_path, manifest_path)

    assert {path.name for path in tmp_path.iterdir()} == before
    assert verification["run"]["mode"] == "verify_only"
    assert verification["output"]["sha256"] == _sha256(patched)
    assert verification["evidence_sha256"] == compute_evidence_sha256(
        verification["evidence"]
    )

    output = tmp_path / "applied.bin"
    receipt = apply_patch_manifest(source_path, manifest_path, output)
    assert receipt["evidence"] == verification["evidence"]
    assert receipt["evidence_sha256"] == verification["evidence_sha256"]


def test_evidence_is_canonical_across_different_output_paths(tmp_path):
    _source, _patched, _manifest, source_path, manifest_path = _case(tmp_path)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()

    first = apply_patch_manifest(source_path, manifest_path, first_dir / "one.bin")
    second = apply_patch_manifest(source_path, manifest_path, second_dir / "two.bin")

    assert first["run"]["output_path"] != second["run"]["output_path"]
    assert first["evidence"] == second["evidence"]
    assert first["evidence_sha256"] == second["evidence_sha256"]
    assert first["evidence_sha256"] == compute_evidence_sha256(first["evidence"])


def test_manifest_is_parsed_and_hashed_from_one_read(tmp_path, monkeypatch):
    _source, _patched, _manifest, source_path, manifest_path = _case(tmp_path)
    original_read_bytes = Path.read_bytes
    reads = {manifest_path.resolve(): 0}

    def counted_read_bytes(path):
        resolved = path.resolve()
        if resolved in reads:
            reads[resolved] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)
    verification = verify_patch_manifest(source_path, manifest_path)

    assert reads[manifest_path.resolve()] == 1
    assert verification["evidence"]["manifest"]["sha256"] == _sha256(
        manifest_path.read_bytes()
    )


def _sum8_verifier(image, context):
    covered = context["covered_ranges"]
    stored = context["stored_ranges"]
    assert len(covered) == 1
    assert len(stored) == 1
    covered_bytes = image[
        covered[0]["offset"]:covered[0]["offset"] + covered[0]["length"]
    ]
    stored_bytes = image[
        stored[0]["offset"]:stored[0]["offset"] + stored[0]["length"]
    ]
    computed = sum(covered_bytes) & 0xFF
    actual = stored_bytes[0]
    return {
        "valid": computed == actual,
        "computed_hex": f"{computed:02X}",
        "stored_hex": f"{actual:02X}",
    }


def _checksum_case(tmp_path):
    source, _patched, manifest, source_path, manifest_path = _case(tmp_path)
    source = bytearray(source)
    source[63] = sum(source[:63]) & 0xFF
    patched = bytearray(source)
    for chunk in manifest["chunks"]:
        offset = int(chunk["offset"], 16) if isinstance(chunk["offset"], str) else chunk["offset"]
        replacement = bytes.fromhex(chunk["replacement_hex"])
        patched[offset:offset + len(replacement)] = replacement
    patched[63] = sum(patched[:63]) & 0xFF
    manifest["chunks"].append(
        {
            "name": "checksum-byte",
            "kind": "checksum",
            "offset": 63,
            "expected_hex": bytes(source[63:64]).hex().upper(),
            "replacement_hex": bytes(patched[63:64]).hex().upper(),
        }
    )
    manifest["target"]["base_sha256"] = _sha256(bytes(source))
    manifest["target"]["patched_sha256"] = _sha256(bytes(patched))
    manifest["checksum"] = {
        "profile": "test.sum8.v1",
        "covered_ranges": [{"offset": 0, "length": 63}],
        "stored_ranges": [{"offset": 63, "length": 1}],
        "parameters": {"algorithm": "sum8"},
    }
    source_path.write_bytes(source)
    _write_manifest(manifest_path, manifest)
    return bytes(source), bytes(patched), manifest, source_path, manifest_path


def test_requested_checksum_profile_fails_closed_when_unavailable(tmp_path):
    _source, _patched, _manifest, source_path, manifest_path = _checksum_case(tmp_path)
    output = tmp_path / "must-not-exist.bin"

    with pytest.raises(PatchManifestError, match="no trusted verifier is available"):
        apply_patch_manifest(source_path, manifest_path, output)

    assert not output.exists()
    assert not Path(str(output) + ".receipt.json").exists()


def test_trusted_checksum_verifier_records_input_and_output_results(tmp_path):
    source, patched, _manifest, source_path, manifest_path = _checksum_case(tmp_path)
    registry = {"test.sum8.v1": _sum8_verifier}

    verification = verify_patch_manifest(
        source_path, manifest_path, checksum_verifiers=registry
    )

    checksum = verification["evidence"]["checksum"]
    assert checksum["parameters"] == {"algorithm": "sum8"}
    assert checksum["input"]["status"] == "passed"
    assert checksum["output"]["status"] == "passed"
    assert checksum["input"]["result"]["stored_hex"] == f"{source[63]:02X}"
    assert checksum["output"]["result"]["stored_hex"] == f"{patched[63]:02X}"
    assert verification["proof"]["checksum_status"] == "passed"

    output = tmp_path / "checksummed.bin"
    receipt = apply_patch_manifest(
        source_path,
        manifest_path,
        output,
        checksum_verifiers=registry,
    )
    assert output.read_bytes() == patched
    assert receipt["evidence_sha256"] == verification["evidence_sha256"]


def test_checksum_failure_and_callback_exception_fail_closed(tmp_path):
    _source, _patched, _manifest, source_path, manifest_path = _checksum_case(tmp_path)

    with pytest.raises(PatchManifestError, match="failed for input image"):
        verify_patch_manifest(
            source_path,
            manifest_path,
            checksum_verifiers={"test.sum8.v1": lambda _image, _context: {"valid": False}},
        )

    def broken_verifier(_image, _context):
        raise RuntimeError("test failure")

    with pytest.raises(PatchManifestError, match="verifier failed: test failure"):
        verify_patch_manifest(
            source_path,
            manifest_path,
            checksum_verifiers={"test.sum8.v1": broken_verifier},
        )


def test_manifest_cannot_request_an_external_checksum_command(tmp_path):
    _source, _patched, manifest, _source_path, manifest_path = _checksum_case(tmp_path)
    manifest["checksum"]["command"] = "untrusted-tool --rewrite"
    _write_manifest(manifest_path, manifest)

    with pytest.raises(PatchManifestError, match="unknown checksum field.*command"):
        load_patch_manifest(manifest_path)

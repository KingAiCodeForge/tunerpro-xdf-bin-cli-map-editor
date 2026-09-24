"""Strict, reversible raw-byte patch manifests for exact ECU images.

Version 2 binds a patch to semantic target identity, generic binary identity
probes, named immutable ranges and exact whole-file hashes. Optional checksum
verification is selected by a manifest profile name but implemented only by a
trusted in-process callback supplied by the caller. The manifest never names
or executes an external command and this module does not repair checksums.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Tuple


SCHEMA = "kingai.raw-patch.v2"
LEGACY_SCHEMA = "kingai.raw-patch.v1"
EVIDENCE_SCHEMA = "kingai.raw-patch-evidence.v2"
RECEIPT_SCHEMA = "kingai.raw-patch-receipt.v2"
VERIFICATION_SCHEMA = "kingai.raw-patch-verification.v2"
ADDRESS_SPACE = "file_offset"
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX_RE = re.compile(r"^[0-9a-fA-F]+$")
_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")

ChecksumVerifier = Callable[[bytes, Mapping[str, Any]], Mapping[str, Any]]


class PatchManifestError(ValueError):
    """Raised when a manifest or patch result fails a strict safety gate."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _canonical_json_bytes(value: Any) -> bytes:
    """Return the one canonical JSON representation used for evidence hashes."""
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PatchManifestError(f"value is not canonical JSON data: {exc}") from exc


def compute_evidence_sha256(evidence: Mapping[str, Any]) -> str:
    """Hash deterministic evidence independently of run time and file paths."""
    return _sha256(_canonical_json_bytes(evidence))


def _parse_offset(value: Any, field: str = "offset") -> int:
    if isinstance(value, bool):
        raise PatchManifestError(f"{field} must be an integer or 0x-prefixed string")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.startswith(("0x", "0X")):
        try:
            result = int(value, 16)
        except ValueError as exc:
            raise PatchManifestError(f"{field} has invalid hexadecimal value {value!r}") from exc
    else:
        raise PatchManifestError(f"{field} must be an integer or 0x-prefixed string")
    if result < 0:
        raise PatchManifestError(f"{field} must not be negative")
    return result


def _parse_length(value: Any, field: str) -> int:
    result = _parse_offset(value, field)
    if result <= 0:
        raise PatchManifestError(f"{field} must be positive")
    return result


def _decode_hex(value: Any, field: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise PatchManifestError(f"{field} must be a non-empty hexadecimal string")
    if len(value) % 2 or not _HEX_RE.fullmatch(value):
        raise PatchManifestError(f"{field} must contain an even number of hexadecimal digits")
    return bytes.fromhex(value)


def _reject_unknown_keys(obj: Mapping[str, Any], allowed: Iterable[str], where: str) -> None:
    unknown = sorted(set(obj) - set(allowed))
    if unknown:
        raise PatchManifestError(f"unknown {where} field(s): {', '.join(unknown)}")


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise PatchManifestError(f"{field} must be exactly 64 hexadecimal characters")
    return value.upper()


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PatchManifestError(f"{field} must be a non-empty string")
    return value


def _reject_duplicate_object_keys(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PatchManifestError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_json_constant(value: str) -> None:
    raise PatchManifestError(f"non-standard JSON constant {value!r} is not allowed")


def _assert_nonoverlapping(
    intervals: Sequence[Tuple[int, int, str]], where: str
) -> None:
    ordered = sorted(intervals)
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] < previous[1]:
            raise PatchManifestError(
                f"overlapping {where} {previous[2]!r} and {current[2]!r}"
            )


def _assert_disjoint(
    left: Sequence[Tuple[int, int, str]],
    right: Sequence[Tuple[int, int, str]],
    left_name: str,
    right_name: str,
) -> None:
    for left_start, left_end, left_label in left:
        for right_start, right_end, right_label in right:
            if left_start < right_end and right_start < left_end:
                raise PatchManifestError(
                    f"{left_name} {left_label!r} overlaps {right_name} {right_label!r}"
                )


def _normalize_plain_range(value: Any, where: str, size: int) -> Dict[str, int]:
    if not isinstance(value, dict):
        raise PatchManifestError(f"{where} must be a JSON object")
    _reject_unknown_keys(value, {"offset", "length"}, where)
    offset = _parse_offset(value.get("offset"), f"{where}.offset")
    length = _parse_length(value.get("length"), f"{where}.length")
    if offset + length > size:
        raise PatchManifestError(f"{where} extends beyond target.size")
    value["offset"] = offset
    value["length"] = length
    return value


def _parse_patch_manifest_bytes(data: bytes, source: str = "<bytes>") -> Dict[str, Any]:
    """Parse and fully validate one already-read v2 manifest byte buffer."""
    try:
        text = data.decode("utf-8")
        root = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_nonstandard_json_constant,
        )
    except PatchManifestError:
        raise
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PatchManifestError(f"cannot parse manifest {source}: {exc}") from exc
    if not isinstance(root, dict):
        raise PatchManifestError("manifest root must be a JSON object")
    if root.get("schema") == LEGACY_SCHEMA:
        raise PatchManifestError(
            "kingai.raw-patch.v1 is rejected because it lacks required target layout, "
            "generic identity probes and explicit immutable ranges; rebuild it as v2"
        )
    _reject_unknown_keys(
        root,
        {
            "schema",
            "patch_id",
            "description",
            "address_space",
            "target",
            "chunks",
            "immutable_ranges",
            "checksum",
        },
        "top-level",
    )
    if root.get("schema") != SCHEMA:
        raise PatchManifestError(f"schema must be {SCHEMA!r}")
    _require_text(root.get("patch_id"), "patch_id")
    if root.get("address_space") != ADDRESS_SPACE:
        raise PatchManifestError("address_space must be 'file_offset'")
    if "description" in root and not isinstance(root["description"], str):
        raise PatchManifestError("description must be a string")

    target = root.get("target")
    if not isinstance(target, dict):
        raise PatchManifestError("target must be a JSON object")
    _reject_unknown_keys(
        target,
        {
            "ecu",
            "software_id",
            "image_layout",
            "architecture",
            "parent_filename",
            "size",
            "base_sha256",
            "patched_sha256",
            "identity_probes",
        },
        "target",
    )
    for field in (
        "ecu",
        "software_id",
        "image_layout",
        "architecture",
        "parent_filename",
    ):
        _require_text(target.get(field), f"target.{field}")
    if any(separator in target["parent_filename"] for separator in ("/", "\\")):
        raise PatchManifestError("target.parent_filename must be a filename, not a path")
    size = target.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise PatchManifestError("target.size must be a positive integer")
    target["base_sha256"] = _require_sha256(
        target.get("base_sha256"), "target.base_sha256"
    )
    target["patched_sha256"] = _require_sha256(
        target.get("patched_sha256"), "target.patched_sha256"
    )
    if target["base_sha256"] == target["patched_sha256"]:
        raise PatchManifestError("base_sha256 and patched_sha256 must differ")

    probes = target.get("identity_probes")
    if not isinstance(probes, list) or not probes:
        raise PatchManifestError("target.identity_probes must be a non-empty JSON array")
    probe_names = set()
    probe_intervals: List[Tuple[int, int, str]] = []
    for index, probe in enumerate(probes):
        where = f"target.identity_probes[{index}]"
        if not isinstance(probe, dict):
            raise PatchManifestError(f"{where} must be a JSON object")
        _reject_unknown_keys(probe, {"name", "description", "offset", "expected_hex"}, where)
        name = _require_text(probe.get("name"), f"{where}.name")
        if name in probe_names:
            raise PatchManifestError(f"duplicate identity probe name {name!r}")
        probe_names.add(name)
        if "description" in probe and not isinstance(probe["description"], str):
            raise PatchManifestError(f"{where}.description must be a string")
        offset = _parse_offset(probe.get("offset"), f"{where}.offset")
        expected = _decode_hex(probe.get("expected_hex"), f"{where}.expected_hex")
        if offset + len(expected) > size:
            raise PatchManifestError(f"{where} extends beyond target.size")
        probe["offset"] = offset
        probe["expected_hex"] = expected.hex().upper()
        probe["_expected"] = expected
        probe_intervals.append((offset, offset + len(expected), name))
    _assert_nonoverlapping(probe_intervals, "identity probes")

    chunks = root.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise PatchManifestError("chunks must be a non-empty JSON array")
    chunk_names = set()
    chunk_intervals: List[Tuple[int, int, str]] = []
    for index, chunk in enumerate(chunks):
        where = f"chunks[{index}]"
        if not isinstance(chunk, dict):
            raise PatchManifestError(f"{where} must be a JSON object")
        _reject_unknown_keys(
            chunk,
            {"name", "description", "kind", "offset", "expected_hex", "replacement_hex"},
            where,
        )
        name = _require_text(chunk.get("name"), f"{where}.name")
        if name in chunk_names:
            raise PatchManifestError(f"duplicate chunk name {name!r}")
        chunk_names.add(name)
        if "description" in chunk and not isinstance(chunk["description"], str):
            raise PatchManifestError(f"{where}.description must be a string")
        if "kind" in chunk and not isinstance(chunk["kind"], str):
            raise PatchManifestError(f"{where}.kind must be a string")
        offset = _parse_offset(chunk.get("offset"), f"{where}.offset")
        before = _decode_hex(chunk.get("expected_hex"), f"{where}.expected_hex")
        after = _decode_hex(chunk.get("replacement_hex"), f"{where}.replacement_hex")
        if len(before) != len(after):
            raise PatchManifestError(f"{where} expected/replacement lengths differ")
        if before == after:
            raise PatchManifestError(f"{where} does not change any byte")
        if offset + len(before) > size:
            raise PatchManifestError(f"{where} extends beyond target.size")
        chunk["offset"] = offset
        chunk["expected_hex"] = before.hex().upper()
        chunk["replacement_hex"] = after.hex().upper()
        chunk["_expected"] = before
        chunk["_replacement"] = after
        chunk_intervals.append((offset, offset + len(before), name))
    _assert_nonoverlapping(chunk_intervals, "chunks")
    _assert_disjoint(probe_intervals, chunk_intervals, "identity probe", "chunk")

    immutable_ranges = root.get("immutable_ranges")
    if not isinstance(immutable_ranges, list) or not immutable_ranges:
        raise PatchManifestError("immutable_ranges must be a non-empty JSON array")
    immutable_names = set()
    immutable_intervals: List[Tuple[int, int, str]] = []
    for index, immutable in enumerate(immutable_ranges):
        where = f"immutable_ranges[{index}]"
        if not isinstance(immutable, dict):
            raise PatchManifestError(f"{where} must be a JSON object")
        _reject_unknown_keys(immutable, {"name", "description", "offset", "length", "sha256"}, where)
        name = _require_text(immutable.get("name"), f"{where}.name")
        if name in immutable_names:
            raise PatchManifestError(f"duplicate immutable range name {name!r}")
        immutable_names.add(name)
        if "description" in immutable and not isinstance(immutable["description"], str):
            raise PatchManifestError(f"{where}.description must be a string")
        offset = _parse_offset(immutable.get("offset"), f"{where}.offset")
        length = _parse_length(immutable.get("length"), f"{where}.length")
        if offset + length > size:
            raise PatchManifestError(f"{where} extends beyond target.size")
        immutable["offset"] = offset
        immutable["length"] = length
        immutable["sha256"] = _require_sha256(immutable.get("sha256"), f"{where}.sha256")
        immutable_intervals.append((offset, offset + length, name))
    _assert_nonoverlapping(immutable_intervals, "immutable ranges")
    _assert_disjoint(immutable_intervals, chunk_intervals, "immutable range", "chunk")

    checksum = root.get("checksum")
    if checksum is not None:
        if not isinstance(checksum, dict):
            raise PatchManifestError("checksum must be a JSON object")
        _reject_unknown_keys(
            checksum,
            {"profile", "covered_ranges", "stored_ranges", "parameters"},
            "checksum",
        )
        profile = _require_text(checksum.get("profile"), "checksum.profile")
        if not _PROFILE_RE.fullmatch(profile):
            raise PatchManifestError("checksum.profile contains unsupported characters")
        for collection_name in ("covered_ranges", "stored_ranges"):
            values = checksum.get(collection_name)
            if not isinstance(values, list) or not values:
                raise PatchManifestError(f"checksum.{collection_name} must be a non-empty array")
            intervals = []
            for index, value in enumerate(values):
                where = f"checksum.{collection_name}[{index}]"
                normalized = _normalize_plain_range(value, where, size)
                intervals.append(
                    (
                        normalized["offset"],
                        normalized["offset"] + normalized["length"],
                        str(index),
                    )
                )
            _assert_nonoverlapping(intervals, f"checksum {collection_name}")
        parameters = checksum.get("parameters", {})
        if not isinstance(parameters, dict):
            raise PatchManifestError("checksum.parameters must be a JSON object")
        _canonical_json_bytes(parameters)
        checksum["parameters"] = parameters

    return root


def load_patch_manifest(path: str | Path) -> Dict[str, Any]:
    """Read exactly once and fully validate a strict v2 raw-patch manifest."""
    manifest_path = Path(path)
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise PatchManifestError(f"cannot read manifest {manifest_path}: {exc}") from exc
    return _parse_patch_manifest_bytes(manifest_bytes, str(manifest_path))


def _ranges_from_offsets(offsets: Sequence[int]) -> List[Dict[str, Any]]:
    if not offsets:
        return []
    ranges = []
    start = previous = offsets[0]
    for offset in offsets[1:]:
        if offset != previous + 1:
            ranges.append({"start": start, "end": previous, "length": previous - start + 1})
            start = offset
        previous = offset
    ranges.append({"start": start, "end": previous, "length": previous - start + 1})
    return ranges


def _prove_bounded_diff(
    source: bytes,
    result: bytes,
    allowed_ranges: Sequence[Tuple[int, int]],
    expected_changed_offsets: Iterable[int],
) -> Dict[str, Any]:
    """Prove exact changed offsets and the absence of out-of-manifest edits."""
    if len(source) != len(result):
        raise PatchManifestError("result size differs from source size")
    changed = {index for index, (a, b) in enumerate(zip(source, result)) if a != b}
    expected = set(expected_changed_offsets)
    if changed != expected:
        missing = sorted(expected - changed)
        extra = sorted(changed - expected)
        raise PatchManifestError(
            f"bounded diff mismatch: {len(missing)} expected changes missing, "
            f"{len(extra)} unexpected changes present"
        )
    allowed = {
        offset
        for start, end_exclusive in allowed_ranges
        for offset in range(start, end_exclusive)
    }
    outside = sorted(changed - allowed)
    if outside:
        raise PatchManifestError(
            f"result changes {len(outside)} byte(s) outside the manifest allowlist"
        )
    changed_sorted = sorted(changed)
    return {
        "changed_bytes": len(changed_sorted),
        "changed_ranges": _ranges_from_offsets(changed_sorted),
        "exact_changed_offsets_matched": True,
        "no_changes_outside_allowlist": True,
    }


def _verify_identity_probes(image: bytes, target: Mapping[str, Any], phase: str) -> List[Dict[str, Any]]:
    receipts = []
    for probe in target["identity_probes"]:
        offset = probe["offset"]
        expected = probe["_expected"]
        actual = image[offset:offset + len(expected)]
        if actual != expected:
            raise PatchManifestError(
                f"{phase} identity probe {probe['name']!r} mismatch at 0x{offset:X}: "
                f"expected {expected.hex().upper()}, got {actual.hex().upper()}"
            )
        receipts.append(
            {
                "name": probe["name"],
                "offset": offset,
                "offset_hex": f"0x{offset:X}",
                "length": len(expected),
                "expected_hex": expected.hex().upper(),
                "matched": True,
            }
        )
    return receipts


def _verify_immutable_ranges(
    source: bytes, result: bytes, manifest: Mapping[str, Any]
) -> List[Dict[str, Any]]:
    receipts = []
    for immutable in manifest["immutable_ranges"]:
        offset = immutable["offset"]
        length = immutable["length"]
        expected_hash = immutable["sha256"]
        source_slice = source[offset:offset + length]
        result_slice = result[offset:offset + length]
        source_hash = _sha256(source_slice)
        result_hash = _sha256(result_slice)
        if source_hash != expected_hash:
            raise PatchManifestError(
                f"input immutable range {immutable['name']!r} SHA-256 mismatch: "
                f"expected {expected_hash}, got {source_hash}"
            )
        if result_hash != expected_hash or result_slice != source_slice:
            raise PatchManifestError(f"output immutable range {immutable['name']!r} changed")
        receipts.append(
            {
                "name": immutable["name"],
                "offset": offset,
                "offset_hex": f"0x{offset:X}",
                "length": length,
                "sha256": expected_hash,
                "input_matched": True,
                "output_matched": True,
            }
        )
    return receipts


def _run_checksum_verifier(
    image: bytes,
    checksum: Mapping[str, Any] | None,
    checksum_verifiers: Mapping[str, ChecksumVerifier] | None,
    phase: str,
) -> Dict[str, Any]:
    if checksum is None:
        return {"requested": False, "status": "not_requested"}
    profile = checksum["profile"]
    if checksum_verifiers is None or profile not in checksum_verifiers:
        raise PatchManifestError(
            f"checksum profile {profile!r} was requested but no trusted verifier is available"
        )
    verifier = checksum_verifiers[profile]
    if not callable(verifier):
        raise PatchManifestError(f"trusted checksum verifier {profile!r} is not callable")
    context = {
        "profile": profile,
        "covered_ranges": checksum["covered_ranges"],
        "stored_ranges": checksum["stored_ranges"],
        "parameters": checksum["parameters"],
        "phase": phase,
    }
    callback_context = json.loads(_canonical_json_bytes(context).decode("utf-8"))
    try:
        outcome = verifier(image, callback_context)
    except Exception as exc:
        raise PatchManifestError(
            f"checksum profile {profile!r} {phase} verifier failed: {exc}"
        ) from exc
    if not isinstance(outcome, Mapping):
        raise PatchManifestError(
            f"checksum profile {profile!r} {phase} verifier must return a mapping"
        )
    normalized = json.loads(_canonical_json_bytes(dict(outcome)).decode("utf-8"))
    if normalized.get("valid") is not True:
        raise PatchManifestError(f"checksum profile {profile!r} failed for {phase} image")
    return {
        "requested": True,
        "status": "passed",
        "profile": profile,
        "result": normalized,
    }


def _validate_and_stage(
    source: bytes,
    manifest: Dict[str, Any],
    reverse: bool = False,
    checksum_verifiers: Mapping[str, ChecksumVerifier] | None = None,
) -> Tuple[bytes, Dict[str, Any]]:
    target = manifest["target"]
    direction = "reverse" if reverse else "forward"
    expected_input_hash = target["patched_sha256"] if reverse else target["base_sha256"]
    expected_output_hash = target["base_sha256"] if reverse else target["patched_sha256"]
    if len(source) != target["size"]:
        raise PatchManifestError(
            f"input size mismatch: expected {target['size']}, got {len(source)}"
        )
    input_hash = _sha256(source)
    if input_hash != expected_input_hash:
        raise PatchManifestError(
            f"input SHA-256 mismatch: expected {expected_input_hash}, got {input_hash}"
        )
    input_probes = _verify_identity_probes(source, target, "input")

    staged = bytearray(source)
    allowed_ranges = []
    expected_changed = set()
    chunk_receipts = []
    for chunk in manifest["chunks"]:
        offset = chunk["offset"]
        before = chunk["_replacement"] if reverse else chunk["_expected"]
        after = chunk["_expected"] if reverse else chunk["_replacement"]
        end = offset + len(before)
        actual = bytes(staged[offset:end])
        if actual != before:
            raise PatchManifestError(
                f"chunk {chunk['name']!r} expected bytes do not match at 0x{offset:X}: "
                f"expected {before.hex().upper()}, got {actual.hex().upper()}"
            )
        staged[offset:end] = after
        allowed_ranges.append((offset, end))
        changed_here = [offset + i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        expected_changed.update(changed_here)
        chunk_receipts.append(
            {
                "name": chunk["name"],
                "kind": chunk.get("kind", "raw"),
                "offset": offset,
                "offset_hex": f"0x{offset:X}",
                "length": len(before),
                "before_hex": before.hex().upper(),
                "after_hex": after.hex().upper(),
                "manifest_expected_hex": chunk["expected_hex"],
                "manifest_replacement_hex": chunk["replacement_hex"],
                "changed_bytes": len(changed_here),
            }
        )

    result = bytes(staged)
    output_probes = _verify_identity_probes(result, target, "output")
    proof = _prove_bounded_diff(source, result, allowed_ranges, expected_changed)
    output_hash = _sha256(result)
    if output_hash != expected_output_hash:
        raise PatchManifestError(
            f"result SHA-256 mismatch: expected {expected_output_hash}, got {output_hash}"
        )
    immutable_receipts = _verify_immutable_ranges(source, result, manifest)
    checksum = manifest.get("checksum")
    checksum_receipt = {
        "profile": checksum["profile"] if checksum else None,
        "covered_ranges": checksum["covered_ranges"] if checksum else [],
        "stored_ranges": checksum["stored_ranges"] if checksum else [],
        "parameters": checksum["parameters"] if checksum else {},
        "input": _run_checksum_verifier(source, checksum, checksum_verifiers, "input"),
        "output": _run_checksum_verifier(result, checksum, checksum_verifiers, "output"),
    }
    checksum_status = "passed" if checksum else "not_requested"
    return result, {
        "direction": direction,
        "input_sha256": input_hash,
        "output_sha256": output_hash,
        "identity_probes": input_probes,
        "output_identity_probes": output_probes,
        "chunks": chunk_receipts,
        "immutable_ranges": immutable_receipts,
        "checksum": checksum_receipt,
        "allowlist_ranges": [
            {"start": start, "end": end - 1, "length": end - start}
            for start, end in allowed_ranges
        ],
        "proof": {
            "all_expected_bytes_matched": True,
            "all_identity_probes_matched": True,
            "all_immutable_ranges_matched": True,
            "checksum_status": checksum_status,
            "result_sha256_matched": True,
            **proof,
        },
    }


def _target_evidence(target: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "ecu": target["ecu"],
        "software_id": target["software_id"],
        "image_layout": target["image_layout"],
        "architecture": target["architecture"],
        "parent_filename": target["parent_filename"],
        "size": target["size"],
        "base_sha256": target["base_sha256"],
        "patched_sha256": target["patched_sha256"],
    }


def _build_evidence(
    source: bytes,
    result: bytes,
    manifest: Mapping[str, Any],
    manifest_sha256: str,
    staged: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema": EVIDENCE_SCHEMA,
        "patch_id": manifest["patch_id"],
        "direction": staged["direction"],
        "address_space": ADDRESS_SPACE,
        "manifest": {"schema": manifest["schema"], "sha256": manifest_sha256},
        "target": _target_evidence(manifest["target"]),
        "input": {"size": len(source), "sha256": staged["input_sha256"]},
        "output": {"size": len(result), "sha256": staged["output_sha256"]},
        "identity_probes": staged["identity_probes"],
        "output_identity_probes": staged["output_identity_probes"],
        "chunks": staged["chunks"],
        "immutable_ranges": staged["immutable_ranges"],
        "checksum": staged["checksum"],
        "allowlist_ranges": staged["allowlist_ranges"],
        "proof": staged["proof"],
    }


def _read_and_verify(
    input_path: str | Path,
    manifest_path: str | Path,
    reverse: bool,
    checksum_verifiers: Mapping[str, ChecksumVerifier] | None,
) -> Tuple[Path, Path, bytes, bytes, Dict[str, Any], bytes, Dict[str, Any], Dict[str, Any]]:
    source_path = Path(input_path).resolve()
    manifest_file = Path(manifest_path).resolve()
    try:
        source = source_path.read_bytes()
        manifest_bytes = manifest_file.read_bytes()
    except OSError as exc:
        raise PatchManifestError(str(exc)) from exc
    # Parse and hash the exact same immutable byte buffer. Do not reread it.
    manifest = _parse_patch_manifest_bytes(manifest_bytes, str(manifest_file))
    if not reverse and source_path.name != manifest["target"]["parent_filename"]:
        raise PatchManifestError(
            "input parent filename mismatch: expected "
            f"{manifest['target']['parent_filename']!r}, got {source_path.name!r}"
        )
    result, staged = _validate_and_stage(
        source,
        manifest,
        reverse=reverse,
        checksum_verifiers=checksum_verifiers,
    )
    evidence = _build_evidence(source, result, manifest, _sha256(manifest_bytes), staged)
    return (
        source_path,
        manifest_file,
        source,
        manifest_bytes,
        manifest,
        result,
        staged,
        evidence,
    )


def verify_patch_manifest(
    input_path: str | Path,
    manifest_path: str | Path,
    reverse: bool = False,
    checksum_verifiers: Mapping[str, ChecksumVerifier] | None = None,
) -> Dict[str, Any]:
    """Validate and stage a patch entirely in memory without writing files."""
    (
        source_path,
        manifest_file,
        _source,
        _manifest_bytes,
        _manifest,
        _result,
        staged,
        evidence,
    ) = _read_and_verify(input_path, manifest_path, reverse, checksum_verifiers)
    return {
        "schema": VERIFICATION_SCHEMA,
        "evidence": evidence,
        "evidence_sha256": compute_evidence_sha256(evidence),
        "patch_id": evidence["patch_id"],
        "direction": evidence["direction"],
        "input": evidence["input"],
        "output": evidence["output"],
        "proof": staged["proof"],
        "run": {
            "mode": "verify_only",
            "input_path": str(source_path),
            "manifest_path": str(manifest_file),
        },
    }


def apply_patch_manifest(
    input_path: str | Path,
    manifest_path: str | Path,
    output_path: str | Path,
    receipt_path: str | Path | None = None,
    reverse: bool = False,
    checksum_verifiers: Mapping[str, ChecksumVerifier] | None = None,
) -> Dict[str, Any]:
    """Apply a strict manifest and write a new BIN plus JSON receipt."""
    source_path = Path(input_path).resolve()
    manifest_file = Path(manifest_path).resolve()
    destination = Path(output_path).resolve()
    receipt_file = (
        Path(receipt_path).resolve()
        if receipt_path is not None
        else Path(str(destination) + ".receipt.json")
    )
    protected_paths = {source_path, manifest_file}
    if destination in protected_paths:
        raise PatchManifestError("output must differ from the input BIN and manifest")
    if receipt_file in protected_paths or receipt_file == destination:
        raise PatchManifestError("receipt path must be separate from input, manifest and output")
    if destination.exists():
        raise PatchManifestError(f"refusing to overwrite existing output {destination}")
    if receipt_file.exists():
        raise PatchManifestError(f"refusing to overwrite existing receipt {receipt_file}")
    if not destination.parent.is_dir():
        raise PatchManifestError(f"output directory does not exist: {destination.parent}")
    if not receipt_file.parent.is_dir():
        raise PatchManifestError(f"receipt directory does not exist: {receipt_file.parent}")

    (
        verified_source_path,
        verified_manifest_file,
        source,
        _manifest_bytes,
        manifest,
        result,
        staged,
        evidence,
    ) = _read_and_verify(source_path, manifest_file, reverse, checksum_verifiers)
    evidence_hash = compute_evidence_sha256(evidence)
    run = {
        "mode": "apply",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(verified_source_path),
        "manifest_path": str(verified_manifest_file),
        "output_path": str(destination),
        "receipt_path": str(receipt_file),
    }

    # Keep the original top-level projection for existing CLI callers. The
    # canonical path-free evidence object is the only value covered by its hash.
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "evidence": evidence,
        "evidence_sha256": evidence_hash,
        "run": run,
        "patch_id": manifest["patch_id"],
        "direction": staged["direction"],
        "manifest": {"path": str(verified_manifest_file), **evidence["manifest"]},
        "input": {
            "path": str(verified_source_path),
            **evidence["input"],
            "osid": manifest["target"]["software_id"],
        },
        "output": {
            "path": str(destination),
            **evidence["output"],
            "osid": manifest["target"]["software_id"],
        },
        "chunks": staged["chunks"],
        "immutable_ranges": staged["immutable_ranges"],
        "checksum": staged["checksum"],
        "allowlist_ranges": staged["allowlist_ranges"],
        "proof": staged["proof"],
    }

    wrote_output = False
    wrote_receipt = False
    try:
        with destination.open("xb") as handle:
            wrote_output = True
            handle.write(result)
            handle.flush()
            os.fsync(handle.fileno())
        disk_result = destination.read_bytes()
        if disk_result != result or _sha256(disk_result) != staged["output_sha256"]:
            raise PatchManifestError("disk reread differs from the staged result")
        receipt["run"]["output_reread_verified"] = True
        with receipt_file.open("x", encoding="utf-8", newline="\n") as handle:
            wrote_receipt = True
            json.dump(receipt, handle, indent=2, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if wrote_output:
            destination.unlink(missing_ok=True)
        if wrote_receipt:
            receipt_file.unlink(missing_ok=True)
        raise
    return receipt


__all__ = [
    "ADDRESS_SPACE",
    "ChecksumVerifier",
    "EVIDENCE_SCHEMA",
    "PatchManifestError",
    "RECEIPT_SCHEMA",
    "SCHEMA",
    "VERIFICATION_SCHEMA",
    "_prove_bounded_diff",
    "_sha256",
    "apply_patch_manifest",
    "compute_evidence_sha256",
    "load_patch_manifest",
    "verify_patch_manifest",
]

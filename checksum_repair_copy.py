"""Opt-in, hash-bound checksum repair-to-copy for ONE known VY $060A profile.

This module does not flash hardware, parse XDFs, change calibration values, or
change the ECU's checksum-gate byte. No arbitrary DLL/script plugins are loaded.
The existing raw_patch_checksum_profiles verifier remains the authority.

ChatGPTz idea 💡: a narrowly allowlisted adapter inspired by the existing
VY additive16 verifier and its original-vs-checksum-control regression pair.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from raw_patch_checksum_profiles import (
    ChecksumProfileError,
    VY_CHECKSUM_CONTRACT,
    VY_CHECKSUM_OFFSET,
    VY_PROFILE_ID,
    VY_IMAGE_SIZE,
    verify_holden_vy_060a_92118883_additive16,
)

SCHEMA = "kingai.checksum-repair-copy.v1"
HASH_RE = re.compile(r"[0-9a-fA-F]{64}\Z")


class ChecksumRepairCopyError(ValueError):
    """Refuse an unsupported or unverified checksum-copy operation."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _context(phase: str) -> dict[str, Any]:
    context = copy.deepcopy(VY_CHECKSUM_CONTRACT)
    context["phase"] = phase
    return context


def _read_image(path: Path) -> bytes:
    """Bound one regular, non-reparse image snapshot before allocating it."""
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode)
            or getattr(before, "st_file_attributes", 0) & 0x400):
        raise ChecksumRepairCopyError("image must be a regular non-reparse file")
    if before.st_size != VY_IMAGE_SIZE:
        raise ChecksumRepairCopyError(f"expected {VY_IMAGE_SIZE}-byte VY full image")

    def identity(value):
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)

    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if identity(opened) != identity(before):
            raise ChecksumRepairCopyError("image changed while opening snapshot")
        image = stream.read(VY_IMAGE_SIZE + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    if (len(image) != VY_IMAGE_SIZE
            or identity(after) != identity(before)
            or identity(current) != identity(before)
            or not stat.S_ISREG(current.st_mode)
            or getattr(current, "st_file_attributes", 0) & 0x400):
        raise ChecksumRepairCopyError("image changed while reading snapshot")
    return image


def _directory_identity(path: Path) -> tuple[int, int]:
    value = path.lstat()
    if (not stat.S_ISDIR(value.st_mode)
            or getattr(value, "st_file_attributes", 0) & 0x400):
        raise ChecksumRepairCopyError("output directory must not be a reparse point")
    return value.st_dev, value.st_ino


def plan_repair_copy(image: bytes, *, expected_sha256: str) -> tuple[bytes, dict[str, Any]]:
    """Propose only the two VY stored-checksum bytes; do not write an output.

    The SHA is an operator-supplied exact input identity, not a claimed stock OS
    ancestry. Target layout, checksum equation and gate are checked again by the
    repository's existing trusted verifier. No byte changes are allowed outside
    the stored-checksum field.
    """
    if not isinstance(image, bytes):
        raise ChecksumRepairCopyError("input image must be immutable bytes")
    if not isinstance(expected_sha256, str) or not HASH_RE.fullmatch(expected_sha256):
        raise ChecksumRepairCopyError("expected_sha256 must be exactly 64 hex digits")
    actual_input_sha = _sha256(image)
    if actual_input_sha != expected_sha256.lower():
        raise ChecksumRepairCopyError("whole-file input SHA-256 mismatch; no repair attempted")

    # Do not accept a caller-supplied checksum formula, offsets or code.
    try:
        before = verify_holden_vy_060a_92118883_additive16(image, _context("input"))
    except ChecksumProfileError as exc:
        raise ChecksumRepairCopyError(f"trusted VY verifier rejected input: {exc}") from exc
    if (before.get("profile") != VY_PROFILE_ID
            or before.get("ecu_checksum_gate", {}).get("state") != "bypass"
            or before.get("ecu_checksum_gate", {}).get("value") != 0xAA):
        raise ChecksumRepairCopyError("unsupported checksum profile/gate semantics")
    records = before.get("records", [])
    if len(records) != 1 or records[0].get("name") != "whole-file":
        raise ChecksumRepairCopyError("unexpected checksum record inventory")
    record = records[0]
    if record.get("record_offset") != VY_CHECKSUM_OFFSET:
        raise ChecksumRepairCopyError("trusted verifier returned unexpected stored offset")
    computed = record.get("computed")
    if type(computed) is not int or not 0 <= computed <= 0xFFFF:
        raise ChecksumRepairCopyError("trusted verifier returned invalid additive-16 value")

    result = bytearray(image)
    result[VY_CHECKSUM_OFFSET:VY_CHECKSUM_OFFSET + 2] = computed.to_bytes(2, "big")
    repaired = bytes(result)
    changed = [i for i, (old, new) in enumerate(zip(image, repaired)) if old != new]
    if not set(changed).issubset({VY_CHECKSUM_OFFSET, VY_CHECKSUM_OFFSET + 1}):
        raise ChecksumRepairCopyError("unexpected non-checksum byte difference")
    try:
        after = verify_holden_vy_060a_92118883_additive16(
            repaired, _context("output")
        )
    except ChecksumProfileError as exc:
        raise ChecksumRepairCopyError(f"trusted verifier rejected repaired image: {exc}") from exc
    if not after.get("valid") or not all(r.get("valid") for r in after.get("records", [])):
        raise ChecksumRepairCopyError("post-repair checksum verification failed")
    if after.get("ecu_checksum_gate") != before.get("ecu_checksum_gate"):
        raise ChecksumRepairCopyError("checksum gate altered unexpectedly")

    receipt = {
        "schema": SCHEMA,
        "target_profile": VY_PROFILE_ID,
        "status": "ALREADY_VALID_NO_WRITE" if not changed else "REPAIR_TO_COPY_REVIEW_ONLY",
        "source_sha256": actual_input_sha,
        "output_sha256": _sha256(repaired),
        "image_bytes": len(image),
        "stored_offset": f"0x{VY_CHECKSUM_OFFSET:05X}",
        "before": {"valid": bool(before["valid"]), "stored_hex": record["stored_hex"],
                   "calculated_hex": record["computed_hex"]},
        "after": {"valid": bool(after["valid"]),
                  "stored_hex": after["records"][0]["stored_hex"]},
        "changed_offsets": [f"0x{i:05X}" for i in changed],
        "changed_bytes": [{"offset": f"0x{i:05X}", "before": f"{image[i]:02X}",
                           "after": f"{repaired[i]:02X}"} for i in changed],
        "gate": {"offset": "0x04008", "value": "0xAA", "state": "bypass",
                 "preserved": True, "ecu_checksum_enforcement_enabled": False},
        "provenance": "SHA-pinned input and trusted verifier; calibration meaning not established",
        "not_qualified": ["firmware-execution", "engine-tuning", "ECU checksum enforcement",
                          "native editor parity", "flash/readback", "hardware safety"],
        "input_file_modified": False,
        "writes_firmware_only_to_new_copy": True,
    }
    return repaired, receipt


def write_repair_package(
    source_path: Path, output_dir: Path, *, expected_sha256: str
) -> dict[str, Any]:
    """Create a new output directory; refuse all existing output destinations.

    This is a review artifact, not an atomic cross-filesystem ECU tool.
    Errors leave the newly created review folder for inspection; the source is
    untouched. Always check the complete receipt before using its output.
    """
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    if not source_path.is_file():
        raise ChecksumRepairCopyError("source must be a regular existing file")
    original = _read_image(source_path)
    repaired, receipt = plan_repair_copy(original, expected_sha256=expected_sha256)
    if not receipt["changed_offsets"]:
        raise ChecksumRepairCopyError("stored checksum already valid: no repair output created")
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    if not output_dir.parent.is_dir():
        raise ChecksumRepairCopyError("output parent directory must already exist")
    _directory_identity(output_dir.parent)
    output_dir.mkdir(exist_ok=False)
    directory_identity = _directory_identity(output_dir)
    out_bin = output_dir / (source_path.stem + ".checksum-copy.bin")
    out_receipt = output_dir / "receipt.json"
    with out_bin.open("xb") as f:
        if f.write(repaired) != len(repaired):
            raise ChecksumRepairCopyError("incomplete checksum-copy write")
        f.flush()
        os.fsync(f.fileno())
    written = _read_image(out_bin)
    if (_sha256(written) != receipt["output_sha256"]
            or written != repaired
            or _read_image(source_path) != original):
        raise ChecksumRepairCopyError("readback or original-preservation check failed")
    # Independent post-write checksum verification, not only prior in-memory proof.
    final = verify_holden_vy_060a_92118883_additive16(
        written, _context("output")
    )
    if not final["valid"]:
        raise ChecksumRepairCopyError("written-copy checksum postflight failed")
    receipt["output_filename"] = out_bin.name
    receipt["source_filename"] = source_path.name
    # A partial JSON write must never appear under the final receipt name.
    pending = output_dir / "receipt.json.pending"
    with pending.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    try:
        staged_receipt = json.loads(pending.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ChecksumRepairCopyError("staged receipt changed before publication") from exc
    if (_directory_identity(output_dir) != directory_identity
            or _read_image(out_bin) != repaired
            or _read_image(source_path) != original
            or staged_receipt != receipt):
        raise ChecksumRepairCopyError("package changed before receipt publication")
    # Linking is atomic and refuses an existing destination on supported local
    # filesystems. No overwrite fallback: unsupported filesystems fail closed.
    os.link(pending, out_receipt)
    pending.unlink()
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", dest="source", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-dir", type=Path,
                        help="Explicit new directory; omit for read-only preview")
    args = parser.parse_args(argv)
    try:
        if args.output_dir is None:
            _, result = plan_repair_copy(_read_image(args.source),
                                         expected_sha256=args.expected_sha256)
        else:
            result = write_repair_package(args.source, args.output_dir,
                                          expected_sha256=args.expected_sha256)
    except (OSError, ChecksumRepairCopyError, ChecksumProfileError) as exc:
        parser.exit(2, f"Checksum repair-copy refused: {exc}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

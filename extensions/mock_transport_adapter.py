"""Source-checkout-only, read-only synthetic transport adapter.

This module does not connect to hardware, enumerate ports, load DLLs, upload an
image or write files. Its `preview-upload` operation validates an immutable
source *request* and emits a deterministic JSON preview receipt. The synthetic
`probe-mock` command is not evidence that a device is present.

ChatGPTz idea: implement the fail-closed mock described in the contributor
hardware roadmap. Inspired by the existing exact-fixture gates and receipt
workflows; it is not a hardware integration or a flash-qualified component.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, Sequence

SCHEMA = "kingai.mock-transport-receipt.v1"
ADAPTER_ID = "kingai.synthetic-eprom-preview.v1"
ADAPTER_VERSION = "0.1.0"
TARGET_ID = "SYNTHETIC-8BIT-ROM-001"
MAX_IMAGE_SIZE = 16 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
SCENARIOS = (
    "ok",
    "disconnect",
    "timeout",
    "duplicate-device",
    "driver-unavailable",
    "unsupported-target",
    "inconclusive-readback",
)
_FAILURES = {
    "disconnect": ("LINK_LOST", "simulated link lost; no operation attempted"),
    "timeout": ("TIMEOUT", "simulated timeout; no operation attempted"),
    "duplicate-device": ("AMBIGUOUS_DEVICE", "simulated multiple devices; no device selected"),
    "driver-unavailable": ("DRIVER_UNAVAILABLE", "simulated driver unavailable"),
    "unsupported-target": ("TARGET_UNSUPPORTED", "simulated target not on allowlist"),
    "inconclusive-readback": (
        "READBACK_INCONCLUSIVE",
        "simulated readback inconclusive; no delivery verified",
    ),
}
_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z", re.ASCII)


class PreviewRefusal(ValueError):
    """A known refusal with a stable machine-readable identifier."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _receipt(operation: str, decision: str, code: str, detail: str,
             evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "adapter_id": ADAPTER_ID,
        "adapter_version": ADAPTER_VERSION,
        "operation": operation,
        "decision": decision,
        "code": code,
        "detail": detail,
        "simulation_only": True,
        "device_connected": False,
        "hardware_writes": 0,
        "file_writes": 0,
        "flash_eligible": False,
        "evidence": evidence or {},
    }
    result["receipt_sha256"] = hashlib.sha256(_canonical_json(result)).hexdigest()
    return result


def validate_receipt(receipt: dict[str, Any]) -> bool:
    """Check schema + self-hash, not a signature or trusted attestation."""
    try:
        fingerprint = receipt["receipt_sha256"]
        copy = dict(receipt)
        del copy["receipt_sha256"]
        return (
            copy["schema"] == SCHEMA
            and copy["adapter_id"] == ADAPTER_ID
            and type(fingerprint) is str
            and bool(_SHA256_PATTERN.fullmatch(fingerprint))
            and hashlib.sha256(_canonical_json(copy)).hexdigest() == fingerprint
        )
    except (KeyError, TypeError, ValueError):
        return False


def probe_mock(scenario: str = "ok") -> dict[str, Any]:
    """Return only a declared synthetic capability, never an actual USB probe."""
    if scenario not in SCENARIOS:
        return _receipt("probe-mock", "REFUSED", "SCENARIO_INVALID", "unknown simulation")
    if scenario != "ok":
        code, detail = _FAILURES[scenario]
        return _receipt("probe-mock", "REFUSED", code, detail)
    return _receipt(
        "probe-mock", "SIMULATED", "MOCK_ONLY", "synthetic descriptor; no device probed",
        {
            "target_id": TARGET_ID,
            "memory_bus_width_bits": 8,
            "declared_capabilities": ["probe_mock", "preview_upload"],
            "physical_hardware_revisions": [],
            "qualified_ecu_ids": [],
            "device_protocol": "none",
            "driver_abi": "not-applicable",
        },
    )


def _file_sha256_readonly(path: Path, expected_size: int) -> str:
    """Hash a bounded regular file with before/after identity checks; never copy it."""
    if path.is_symlink():
        raise PreviewRefusal("LINK_REFUSED", "symbolic-link input is not supported")
    try:
        before_path = path.stat()
        if not stat.S_ISREG(before_path.st_mode):
            raise PreviewRefusal("NOT_REGULAR", "input is not a regular file")
        if before_path.st_size != expected_size:
            raise PreviewRefusal("SIZE_MISMATCH", "source size differs from requested exact size")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            with os.fdopen(fd, "rb") as file:
                fd = -1
                before_fd = os.fstat(file.fileno())
                if not stat.S_ISREG(before_fd.st_mode):
                    raise PreviewRefusal("NOT_REGULAR", "input is not a regular file")
                if before_fd.st_size != expected_size or not _same_file(before_fd, before_path):
                    raise PreviewRefusal("SOURCE_CHANGED", "source changed during admission")
                sha = hashlib.sha256()
                remaining = expected_size
                while remaining:
                    chunk = file.read(min(remaining, CHUNK_SIZE))
                    if not chunk:
                        raise PreviewRefusal("SOURCE_CHANGED", "source truncated during read")
                    sha.update(chunk)
                    remaining -= len(chunk)
                if file.read(1):
                    raise PreviewRefusal("SOURCE_CHANGED", "source size changed during read")
                after_fd = os.fstat(file.fileno())
                if not _same_file(after_fd, before_fd):
                    raise PreviewRefusal("SOURCE_CHANGED", "source changed during read")
            after_path = path.stat()
            if not _same_file(after_path, before_path) or path.is_symlink():
                raise PreviewRefusal("SOURCE_CHANGED", "source path changed during read")
            return sha.hexdigest()
        finally:
            if fd >= 0:
                os.close(fd)
    except PreviewRefusal:
        raise
    except (OSError, ValueError) as exc:
        raise PreviewRefusal("FILE_UNAVAILABLE", "source cannot be opened or checked") from exc


def _same_file(first: os.stat_result, second: os.stat_result) -> bool:
    # Helpful race check, not a cryptographic snapshot or atomic OS guarantee.
    return (
        first.st_dev, first.st_ino, first.st_size, first.st_mtime_ns
    ) == (
        second.st_dev, second.st_ino, second.st_size, second.st_mtime_ns
    )


def preview_upload(path: Path, expected_sha256: str, expected_size: int,
                   bus_width: int = 8, scenario: str = "ok") -> dict[str, Any]:
    """Verify a synthetic handoff request. Nothing is sent or saved."""
    op = "preview-upload"
    try:
        if type(expected_sha256) is not str or not _SHA256_PATTERN.fullmatch(expected_sha256):
            raise PreviewRefusal("HASH_INVALID", "expected SHA-256 must be 64 hexadecimal characters")
        if type(expected_size) is not int or not (1 <= expected_size <= MAX_IMAGE_SIZE):
            raise PreviewRefusal("SIZE_INVALID", "expected size outside supported preview bound")
        if bus_width != 8 or type(bus_width) is not int:
            raise PreviewRefusal("BUS_WIDTH_UNSUPPORTED", "mock target has an 8-bit memory bus only")
        if scenario not in SCENARIOS:
            raise PreviewRefusal("SCENARIO_INVALID", "unknown simulation")
        measured_hash = _file_sha256_readonly(path, expected_size)
        if measured_hash != expected_sha256.lower():
            raise PreviewRefusal("HASH_MISMATCH", "source hash differs from reviewed image")
        evidence = {
            "source_sha256": measured_hash,
            "expected_size_bytes": expected_size,
            "target_id": TARGET_ID,
            "memory_bus_width_bits": bus_width,
            "scenario": scenario,
        }
        if scenario != "ok":
            code, detail = _FAILURES[scenario]
            return _receipt(op, "REFUSED", code, detail, evidence)
        return _receipt(
            op, "SIMULATED", "PREVIEW_ONLY",
            "hash-matched request; no transfer, write or readback performed", evidence,
        )
    except PreviewRefusal as error:
        return _receipt(op, "REFUSED", error.code, str(error))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthetic read-only adapter: no hardware or file writes")
    parser.add_argument("operation", choices=("probe-mock", "preview-upload", "flash", "erase"))
    parser.add_argument("--bin", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-size", type=int)
    parser.add_argument("--bus-width", type=int, default=8)
    parser.add_argument("--scenario", choices=SCENARIOS, default="ok")
    args = parser.parse_args(argv)
    if args.operation in ("flash", "erase"):
        result = _receipt(args.operation, "REFUSED", "HARDWARE_WRITE_DISABLED",
                          "no hardware writer exists in this adapter")
    elif args.operation == "probe-mock":
        result = probe_mock(args.scenario)
    elif args.bin is None or args.expected_sha256 is None or args.expected_size is None:
        result = _receipt(args.operation, "REFUSED", "REQUIRED_INPUT_MISSING",
                          "preview requires --bin, --expected-sha256 and --expected-size")
    else:
        result = preview_upload(args.bin, args.expected_sha256, args.expected_size,
                                args.bus_width, args.scenario)
    print(_canonical_json(result).decode("ascii"))
    return 0 if result["decision"] == "SIMULATED" else 2


if __name__ == "__main__":
    sys.exit(main())

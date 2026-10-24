"""Fail-closed, stdlib-only *simulation* of a future KingAI hardware adapter.

This module NEVER opens a device, loads a DLL, transmits bytes or flashes an ECU.
It verifies the operator-declared identity of a regular local image, then emits
an immutable, deterministic JSON preview receipt. It is an adapter-contract
reference for contributors, not a source of ECU/hardware compatibility claims.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Protocol

SCHEMA = "kingai.hardware-adapter-preview.v1"
PROBE_SCHEMA = "kingai.hardware-adapter-probe.v1"
ERROR_SCHEMA = "kingai.hardware-adapter-error.v1"
ADAPTER_ID = "kingai.mock.read-only-image-v1"
ADAPTER_VERSION = "0.1.0"
MAX_IMAGE_BYTES = 64 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
_TARGET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")


class AdapterRefusal(ValueError):
    """No trustworthy preview can be generated from these inputs."""


class ReadOnlyAdapter(Protocol):
    """Proposed minimal interface; hardware-writing operations are absent."""

    def probe(self) -> dict[str, Any]: ...

    def preview_image(
        self, image_path: Path, *, expected_sha256: str,
        expected_size: int, declared_target_id: str,
    ) -> dict[str, Any]: ...


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _stamp(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        info.st_dev, info.st_ino, info.st_size,
        info.st_mtime_ns, info.st_ctime_ns,
    )


def _bounded_digest(path: Path, expected_size: int) -> str:
    """Read exactly one regular file and reject observable mid-read changes.

    This is a file identity check, NOT proof of which firmware is on an ECU.
    """
    try:
        initial_path = path.stat()
    except OSError as exc:
        raise AdapterRefusal(f"input image inaccessible: {exc}") from exc
    if not stat.S_ISREG(initial_path.st_mode):
        raise AdapterRefusal("input image must be a regular file")
    if initial_path.st_size != expected_size:
        raise AdapterRefusal("input image length does not match expected size")

    digest = hashlib.sha256()
    observed_bytes = 0
    try:
        with path.open("rb") as source:
            fd_before = os.fstat(source.fileno())
            if _stamp(fd_before) != _stamp(initial_path):
                raise AdapterRefusal("input image changed before its read began")
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                observed_bytes += len(chunk)
                if observed_bytes > MAX_IMAGE_BYTES or observed_bytes > expected_size:
                    raise AdapterRefusal("input image exceeded the declared limit")
                digest.update(chunk)
            fd_after = os.fstat(source.fileno())
        final_path = path.stat()
    except OSError as exc:
        raise AdapterRefusal(f"input image read failed: {exc}") from exc
    if observed_bytes != expected_size:
        raise AdapterRefusal("input image truncated during read")
    if not (_stamp(initial_path) == _stamp(fd_before) ==
            _stamp(fd_after) == _stamp(final_path)):
        raise AdapterRefusal("input image changed during read")
    return digest.hexdigest()


class MockReadOnlyAdapter:
    """The only registered adapter: deterministic, disconnected mock."""

    def probe(self) -> dict[str, Any]:
        return {
            "schema": PROBE_SCHEMA,
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "status": "simulated_only",
            "hardware_connected": False,
            "device_identity_verified": False,
            "hardware_writes_supported": False,
            "capabilities": ["probe_mock", "preview_local_image"],
            "external_dll_loaded": False,
            "warning": "No device or ECU was contacted; target compatibility is unknown.",
        }

    def preview_image(
        self, image_path: Path, *, expected_sha256: str,
        expected_size: int, declared_target_id: str,
    ) -> dict[str, Any]:
        if type(expected_size) is not int or not 0 < expected_size <= MAX_IMAGE_BYTES:
            raise AdapterRefusal("expected size must be 1 to 67108864 bytes")
        if type(expected_sha256) is not str or not _SHA256.fullmatch(expected_sha256):
            raise AdapterRefusal("expected SHA-256 must contain exactly 64 hex digits")
        if type(declared_target_id) is not str or not _TARGET_ID.fullmatch(declared_target_id):
            raise AdapterRefusal("declared target ID must be 1-96 safe ASCII characters")
        image_path = Path(image_path)
        observed_sha256 = _bounded_digest(image_path, expected_size)
        if observed_sha256 != expected_sha256.lower():
            raise AdapterRefusal("source image SHA-256 mismatch")
        result = {
            "schema": SCHEMA,
            "adapter_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "operation": "preview_local_image",
            "status": "simulated_only",
            "declared_target_id": declared_target_id,
            "target_identity_verified_on_hardware": False,
            "hardware_connected": False,
            "hardware_write_executed": False,
            "device_readback": "not_performed",
            "checksum_status": "not_assessed",
            "source_image": {
                "filename": image_path.name,
                "size_bytes": expected_size,
                "sha256": observed_sha256.upper(),
                "identity_stable_during_read": True,
            },
            "admission": {
                "expected_size_matched": True,
                "expected_sha256_matched": True,
                "target_compatibility": "not_assessed",
            },
        }
        result["evidence_sha256"] = hashlib.sha256(_canonical(result)).hexdigest().upper()
        return result


# Hard-coded allowlist. No dynamic discovery, third-party execution or DLL loader.
ADAPTERS: dict[str, ReadOnlyAdapter] = {ADAPTER_ID: MockReadOnlyAdapter()}


def get_adapter(adapter_id: str) -> ReadOnlyAdapter:
    try:
        return ADAPTERS[adapter_id]
    except KeyError as exc:
        raise AdapterRefusal("unregistered adapter: no hardware access granted") from exc


def write_receipt_exclusive(path: Path, image_path: Path, receipt: dict[str, Any]) -> None:
    """Optional JSON output only. Exclusive create, never write to input BIN."""
    path = Path(path)
    image_path = Path(image_path)
    if path.resolve() == image_path.resolve():
        raise AdapterRefusal("receipt output aliases the input image")
    # Do not create parent directories as a side effect of a mock preview.
    try:
        with path.open("x", encoding="utf-8", newline="\n") as out:
            out.write(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            out.flush()
            os.fsync(out.fileno())
    except OSError as exc:
        raise AdapterRefusal(f"receipt could not be created exclusively: {exc}") from exc


def _run_command(args: argparse.Namespace) -> int:
    try:
        adapter = get_adapter(args.adapter)
        if args.command == "adapter-probe":
            payload = adapter.probe()
        elif args.command == "adapter-preview":
            payload = adapter.preview_image(
                Path(args.bin), expected_sha256=args.expected_bin_sha256,
                expected_size=args.expected_size, declared_target_id=args.target_id,
            )
            if args.receipt is not None:
                write_receipt_exclusive(Path(args.receipt), Path(args.bin), payload)
        else:
            raise AdapterRefusal("unsupported adapter operation")
    except AdapterRefusal as exc:
        print(json.dumps({
            "schema": ERROR_SCHEMA,
            "status": "refused",
            "reason": str(exc),
            "hardware_write_executed": False,
        }, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def register_subcommands(subparsers: Any) -> None:
    """One argument declaration shared by Editor CLI and standalone smoke CLI."""
    probe = subparsers.add_parser("adapter-probe", help="Probe built-in mock; no hardware")
    probe.add_argument("--adapter", default=ADAPTER_ID, choices=[ADAPTER_ID])
    probe.set_defaults(func=_run_command)

    preview = subparsers.add_parser("adapter-preview", help="Hash-gated local image preview; NO upload")
    preview.add_argument("--adapter", default=ADAPTER_ID, choices=[ADAPTER_ID])
    preview.add_argument("--bin", required=True, help="Owned local BIN to inspect")
    preview.add_argument("--expected-bin-sha256", required=True, help="Full 64-digit source hash")
    preview.add_argument("--expected-size", required=True, type=int, help="Exact BIN byte count")
    preview.add_argument("--target-id", required=True, help="Operator-declared target; NOT hardware-verified")
    preview.add_argument("--receipt", help="Optional JSON receipt; new file only")
    preview.set_defaults(func=_run_command)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="KingAI mock hardware adapter - NO physical hardware I/O"
    )
    register_subcommands(p.add_subparsers(dest="command", required=True))
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

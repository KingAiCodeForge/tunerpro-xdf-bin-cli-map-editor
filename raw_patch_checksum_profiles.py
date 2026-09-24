"""Trusted, read-only checksum profiles for strict raw-patch manifests.

Profiles in this module are executable code reviewed with the patch tool.  A
manifest can select one by ID, but it cannot supply code or alter the proven
checksum contract.  Verifiers never repair or write an image.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


PROFILE_ID = "bmw-ms42-0110c6-crc16-v1"
IMAGE_SIZE = 0x80000
OSID_OFFSET = 0x48008
OSID = b"0110C6"

_RECORDS = (
    {
        "name": "boot",
        "offset": 0x03C24,
        "seed": 0x2D2D,
        "segments": ((0x00000, 0x03C23),),
    },
    {
        "name": "cal",
        "offset": 0x4FEE0,
        "seed": 0x3643,
        "segments": ((0x48000, 0x4F843),),
    },
    {
        "name": "prog",
        "offset": 0x50306,
        "seed": 0x3030,
        "segments": (
            (0x500A4, 0x50305),
            (0x50342, 0x52EFD),
            (0x60000, 0x60C43),
            (0x70000, 0x7EC65),
            (0x11000, 0x1FFFD),
            (0x20000, 0x2FFFD),
            (0x30000, 0x3FFFF),
        ),
    },
)


class ChecksumProfileError(ValueError):
    """Raised when an image or requested checksum contract is not this profile."""


def _build_contract() -> dict[str, Any]:
    """Build a fresh JSON-safe copy of the exact reviewed profile contract."""
    covered_ranges = []
    parameter_records = []
    for record in _RECORDS:
        segments = []
        for start, end in record["segments"]:
            covered_ranges.append({"offset": start, "length": end - start + 1})
            segments.append({"start": start, "end": end})
        parameter_records.append(
            {
                "name": record["name"],
                "offset": record["offset"],
                "seed": record["seed"],
                "segments": segments,
            }
        )
    return {
        "profile": PROFILE_ID,
        "covered_ranges": covered_ranges,
        "stored_ranges": [
            {"offset": record["offset"], "length": 2} for record in _RECORDS
        ],
        "parameters": {
            "algorithm": "crc16-reflected",
            "polynomial": 0x8005,
            "reflected_polynomial": 0xA001,
            "reflect_input": True,
            "reflect_output": False,
            "xor_out": 0,
            "byte_order": "low-to-high",
            "record_endianness": "little",
            "descriptor_end": "inclusive",
            "image_size": IMAGE_SIZE,
            "osid": {"offset": OSID_OFFSET, "ascii": OSID.decode("ascii")},
            "records": parameter_records,
        },
    }


# This is a convenience template for manifest builders.  Verification compares
# against a fresh private construction, so accidental mutation of this exported
# object cannot weaken the trusted profile.
CHECKSUM_CONTRACT = _build_contract()


def _canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ChecksumProfileError(f"checksum contract is not canonical JSON: {exc}") from exc


def _require_exact_contract(context: Mapping[str, Any]) -> None:
    if not isinstance(context, Mapping):
        raise ChecksumProfileError("checksum verifier context must be a mapping")
    required_keys = {"profile", "covered_ranges", "stored_ranges", "parameters", "phase"}
    if set(context) != required_keys:
        missing = sorted(required_keys - set(context))
        extra = sorted(set(context) - required_keys)
        raise ChecksumProfileError(
            f"checksum context keys differ from the trusted contract; missing={missing}, extra={extra}"
        )
    if context["phase"] not in ("input", "output"):
        raise ChecksumProfileError("checksum context phase must be 'input' or 'output'")

    expected = _build_contract()
    requested = {
        "profile": context["profile"],
        "covered_ranges": context["covered_ranges"],
        "stored_ranges": context["stored_ranges"],
        "parameters": context["parameters"],
    }
    if _canonical_json(requested) != _canonical_json(expected):
        raise ChecksumProfileError(
            f"requested checksum contract does not exactly match trusted profile {PROFILE_ID!r}"
        )


_CRC_TABLE = []
for _byte in range(256):
    _crc = _byte
    for _ in range(8):
        _crc = (_crc >> 1) ^ 0xA001 if _crc & 1 else _crc >> 1
    _CRC_TABLE.append(_crc)
_CRC_TABLE = tuple(_CRC_TABLE)


def _crc16(data: bytes, seed: int) -> int:
    crc = seed & 0xFFFF
    for value in data:
        crc = (crc >> 8) ^ _CRC_TABLE[(crc ^ value) & 0xFF]
    return crc & 0xFFFF


def _parse_and_validate_record(
    image: bytes, record: Mapping[str, Any]
) -> tuple[int, list[tuple[int, int]]]:
    offset = record["offset"]
    stored = int.from_bytes(image[offset:offset + 2], "little")
    count = int.from_bytes(image[offset + 2:offset + 4], "little")
    expected_segments = list(record["segments"])
    if count != len(expected_segments):
        raise ChecksumProfileError(
            f"{record['name']} descriptor count mismatch at 0x{offset:05X}: "
            f"expected {len(expected_segments)}, got {count}"
        )

    segments = []
    cursor = offset + 4
    for _ in range(count):
        start = int.from_bytes(image[cursor:cursor + 4], "little")
        end = int.from_bytes(image[cursor + 4:cursor + 8], "little")
        cursor += 8
        if start > end or end >= len(image):
            raise ChecksumProfileError(
                f"{record['name']} has invalid descriptor 0x{start:05X}..0x{end:05X}"
            )
        segments.append((start, end))

    if segments != expected_segments:
        got = ", ".join(f"0x{start:05X}..0x{end:05X}" for start, end in segments)
        wanted = ", ".join(
            f"0x{start:05X}..0x{end:05X}" for start, end in expected_segments
        )
        raise ChecksumProfileError(
            f"{record['name']} descriptor mismatch at 0x{offset:05X}; "
            f"expected {wanted}, got {got}"
        )
    return stored, segments


def verify_bmw_ms42_0110c6_crc16(
    image: bytes, context: Mapping[str, Any]
) -> dict[str, Any]:
    """Verify the exact 512 KiB MS42 0110C6 checksum profile without writes."""
    _require_exact_contract(context)
    if not isinstance(image, (bytes, bytearray, memoryview)):
        raise ChecksumProfileError("image must be bytes-like")
    image = bytes(image)
    if len(image) != IMAGE_SIZE:
        raise ChecksumProfileError(
            f"expected {IMAGE_SIZE}-byte MS42 full image, got {len(image)} bytes"
        )
    actual_osid = image[OSID_OFFSET:OSID_OFFSET + len(OSID)]
    if actual_osid != OSID:
        shown = actual_osid.decode("ascii", errors="replace")
        raise ChecksumProfileError(
            f"unsupported MS42 OSID {shown!r} at 0x{OSID_OFFSET:05X}; expected '0110C6'"
        )

    details = []
    all_valid = True
    for record in _RECORDS:
        stored, segments = _parse_and_validate_record(image, record)
        computed = record["seed"]
        for start, end in segments:
            computed = _crc16(image[start:end + 1], computed)
        valid = computed == stored
        all_valid = all_valid and valid
        details.append(
            {
                "name": record["name"],
                "record_offset": record["offset"],
                "record_offset_hex": f"0x{record['offset']:05X}",
                "seed": record["seed"],
                "seed_hex": f"0x{record['seed']:04X}",
                "stored": stored,
                "stored_hex": f"0x{stored:04X}",
                "computed": computed,
                "computed_hex": f"0x{computed:04X}",
                "valid": valid,
                "segments": [
                    {"start": start, "end": end, "length": end - start + 1}
                    for start, end in segments
                ],
            }
        )

    return {
        "valid": all_valid,
        "profile": PROFILE_ID,
        "image_size": len(image),
        "osid": {
            "offset": OSID_OFFSET,
            "ascii": OSID.decode("ascii"),
            "matched": True,
        },
        "records": details,
    }


TRUSTED_CHECKSUM_VERIFIERS = {
    PROFILE_ID: verify_bmw_ms42_0110c6_crc16,
}


__all__ = [
    "CHECKSUM_CONTRACT",
    "ChecksumProfileError",
    "IMAGE_SIZE",
    "OSID_OFFSET",
    "PROFILE_ID",
    "TRUSTED_CHECKSUM_VERIFIERS",
    "verify_bmw_ms42_0110c6_crc16",
]

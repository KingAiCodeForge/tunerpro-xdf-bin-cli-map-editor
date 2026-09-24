"""Trusted, read-only checksum profiles for strict raw-patch manifests.

Profiles in this module are executable code reviewed with the patch tool.  A
manifest can select one by ID, but it cannot supply code or alter the proven
checksum contract.  Verifiers never repair or write an image.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


PROFILE_ID = "bmw-ms42-0110c6-crc16-v1"
IMAGE_SIZE = 0x80000
OSID_OFFSET = 0x48008
OSID = b"0110C6"

VY_PROFILE_ID = "holden-vy-060a-92118883-additive16-bypass-aware-v1"
VY_IMAGE_SIZE = 0x20000
VY_OSID_OFFSET = 0x07FFC
VY_OSID = 92118883
VY_PROGRAM_ID_OFFSET = 0x04008
VY_PROGRAM_ID_BYTE = 0xAA
VY_CHECKSUM_OFFSET = 0x04006
VY_CHECKSUM_START = 0x02000
VY_CHECKSUM_SKIP_START = 0x04000
VY_CHECKSUM_SKIP_END = 0x04008
VY_CHECKSUM_END = 0x20000

MS43_PROFILE_ID = "bmw-ms43-430069-crc16-v1"
MS43_ALL_CHECKSUMS_PROFILE_ID = "bmw-ms43-430069-all-five-checksums-v1"
MS43_IMAGE_SIZE = 0x80000
MS43_OSID_OFFSET = 0x70008
MS43_OSID = b"430069"
MS43_ADDRESS_MASK = 0x7FFFF
MS43_ADDITIVE_METADATA_OFFSET = 0x6FDB2
MS43_ADDITIVE_METADATA_HEX = (
    "A5A5A5A502FFA5A5A5A502FF00000D00F83B0D0076E80E0078E80E00"
    "C61207001613070094EB070016EE0700FFFF"
)
MS43_ADDITIVE_METADATA_SHA256 = (
    "899633798EDDFEFE096D837CE2E007BC091A047FE33D4FBB780AB35F0F8906C7"
)

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

_MS43_RECORDS = (
    {
        "name": "boot",
        "offset": 0x03C24,
        "seed": 0x2D2D,
        "seed_offset": 0x03FE6,
        "descriptor_segments": ((0x00000, 0x0308D),),
        "file_segments": ((0x00000, 0x0308D),),
    },
    {
        "name": "prog",
        "offset": 0x6FDE0,
        "seed": 0x3030,
        "seed_offset": 0x6FFB6,
        "descriptor_segments": (
            (0x90000, 0x9FFFF),
            (0xA0000, 0xAFFFB),
            (0xB0000, 0xBFCB9),
            (0xC0000, 0xCA8CB),
            (0xD0000, 0xDFFF7),
            (0xE0000, 0xEEFFF),
        ),
        "file_segments": (
            (0x10000, 0x1FFFF),
            (0x20000, 0x2FFFB),
            (0x30000, 0x3FCB9),
            (0x40000, 0x4A8CB),
            (0x50000, 0x5FFF7),
            (0x60000, 0x6EFFF),
        ),
    },
    {
        "name": "cal",
        "offset": 0x73FE0,
        "seed": 0x3936,
        "seed_offset": 0x7000C,
        "descriptor_segments": (
            (0x70000, 0x72FFF),
            (0x74000, 0x7EE17),
        ),
        "file_segments": (
            (0x70000, 0x72FFF),
            (0x74000, 0x7EE17),
        ),
    },
)

_MS43_ADDITIVE_RECORDS = (
    {
        "name": "program-additive32",
        "offset": 0x6FDAE,
        "seed_offset": 0x6FDB2,
        "seed": 0xA5A5A5A5,
        "descriptor_base": 0x6FDAE,
        "descriptor_count": 2,
        "range_descriptor_offset": 0x10,
        "descriptor_segments": (
            (0xD0000, 0xD3BF8),
            (0xEE876, 0xEE878),
        ),
        "file_segments": (
            (0x50000, 0x53BF8),
            (0x6E876, 0x6E878),
        ),
    },
    {
        "name": "calibration-additive32",
        "offset": 0x72FFC,
        "seed_offset": 0x6FDB8,
        "seed": 0xA5A5A5A5,
        "descriptor_base": 0x6FDAE,
        "descriptor_count": 2,
        "range_descriptor_offset": 0x20,
        "descriptor_segments": (
            (0x712C6, 0x71316),
            (0x7EB94, 0x7EE16),
        ),
        "file_segments": (
            (0x712C6, 0x71316),
            (0x7EB94, 0x7EE16),
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


def _build_vy_contract() -> dict[str, Any]:
    """Build the exact reviewed VY $060A whole-file checksum contract."""
    ranges = (
        (VY_CHECKSUM_START, VY_CHECKSUM_SKIP_START),
        (VY_CHECKSUM_SKIP_END, VY_CHECKSUM_END),
    )
    return {
        "profile": VY_PROFILE_ID,
        "covered_ranges": [
            {"offset": start, "length": end - start} for start, end in ranges
        ],
        "stored_ranges": [{"offset": VY_CHECKSUM_OFFSET, "length": 2}],
        "parameters": {
            "algorithm": "unsigned-byte-sum-modulo-65536",
            "accumulator_bits": 16,
            "range_end": "exclusive",
            "record_endianness": "big",
            "image_size": VY_IMAGE_SIZE,
            "osid": {
                "offset": VY_OSID_OFFSET,
                "value": VY_OSID,
                "hex": f"0x{VY_OSID:08X}",
                "endianness": "big",
            },
            "ecu_checksum_gate": {
                "offset": VY_PROGRAM_ID_OFFSET,
                "value": VY_PROGRAM_ID_BYTE,
                "hex": f"0x{VY_PROGRAM_ID_BYTE:02X}",
                "state": "bypass",
                "preserve": True,
            },
            "ranges": [
                {"start": start, "end": end} for start, end in ranges
            ],
            "excluded_range": {
                "start": VY_CHECKSUM_SKIP_START,
                "end": VY_CHECKSUM_SKIP_END,
            },
            "stored_offset": VY_CHECKSUM_OFFSET,
        },
    }


VY_CHECKSUM_CONTRACT = _build_vy_contract()


def _build_ms43_contract() -> dict[str, Any]:
    """Build the exact 512 KiB MS43 430069 CRC16-only contract."""
    covered_ranges = []
    parameter_records = []
    for record in _MS43_RECORDS:
        descriptor_segments = [
            {"start": start, "end": end}
            for start, end in record["descriptor_segments"]
        ]
        file_segments = []
        for start, end in record["file_segments"]:
            covered_ranges.append({"offset": start, "length": end - start + 1})
            file_segments.append({"start": start, "end": end})
        parameter_records.append(
            {
                "name": record["name"],
                "offset": record["offset"],
                "seed": record["seed"],
                "descriptor_segments": descriptor_segments,
                "file_segments": file_segments,
            }
        )
    return {
        "profile": MS43_PROFILE_ID,
        "covered_ranges": covered_ranges,
        "stored_ranges": [
            {"offset": record["offset"], "length": 2}
            for record in _MS43_RECORDS
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
            "image_size": MS43_IMAGE_SIZE,
            "osid": {
                "offset": MS43_OSID_OFFSET,
                "ascii": MS43_OSID.decode("ascii"),
            },
            "program_descriptor_file_delta": -0x80000,
            "scope": "boot/program/calibration CRC16 records only",
            "excluded_checksum_layers": [
                {
                    "name": "program additive monitor",
                    "offset": 0x6FDAE,
                    "status": "not verified by this profile",
                },
                {
                    "name": "calibration additive monitor",
                    "offset": 0x72FFC,
                    "status": "not verified by this profile",
                },
            ],
            "records": parameter_records,
        },
    }


MS43_CHECKSUM_CONTRACT = _build_ms43_contract()


def _build_ms43_all_checksums_contract() -> dict[str, Any]:
    """Build the exact MS43 430069 three-CRC plus two-additive contract."""
    covered_ranges = []
    records = []
    crc_coverage = []
    for record in _MS43_RECORDS:
        descriptor_segments = [
            {"start": start, "end": end}
            for start, end in record["descriptor_segments"]
        ]
        file_segments = []
        for start, end in record["file_segments"]:
            covered_ranges.append({"offset": start, "length": end - start + 1})
            crc_coverage.append((start, end + 1))
            file_segments.append({"start": start, "end": end})
        records.append(
            {
                "name": record["name"],
                "algorithm": "crc16-reflected",
                "stored_offset": record["offset"],
                "stored_length": 2,
                "seed_offset": record["seed_offset"],
                "seed": record["seed"],
                "descriptor_count_offset": record["offset"] + 2,
                "descriptor_count": len(record["descriptor_segments"]),
                "descriptor_segments": descriptor_segments,
                "file_segments": file_segments,
            }
        )

    for record in _MS43_ADDITIVE_RECORDS:
        file_segments = [
            {"start": start, "end": end}
            for start, end in record["file_segments"]
        ]
        for segment in file_segments:
            if not any(
                cover_start <= segment["start"]
                and segment["end"] <= cover_end
                for cover_start, cover_end in crc_coverage
            ):
                raise AssertionError(
                    f"MS43 additive range is missing from covered-range union: {segment}"
                )
        records.append(
            {
                "name": record["name"],
                "algorithm": "additive32-le16-word-sum",
                "stored_offset": record["offset"],
                "stored_length": 4,
                "seed_offset": record["seed_offset"],
                "seed": record["seed"],
                "descriptor_base": record["descriptor_base"],
                "descriptor_count": record["descriptor_count"],
                "range_descriptor_offset": record["range_descriptor_offset"],
                "descriptor_segments": [
                    {"start": start, "end": end}
                    for start, end in record["descriptor_segments"]
                ],
                "file_segments": file_segments,
            }
        )

    stored_ranges = sorted(
        [
            {"offset": record["offset"], "length": 2}
            for record in _MS43_RECORDS
        ]
        + [
            {"offset": record["offset"], "length": 4}
            for record in _MS43_ADDITIVE_RECORDS
        ],
        key=lambda item: item["offset"],
    )
    return {
        "profile": MS43_ALL_CHECKSUMS_PROFILE_ID,
        # The additive data ranges are strict subsets of the CRC data ranges.
        # The schema requires non-overlapping coverage, so this is their union.
        "covered_ranges": covered_ranges,
        "stored_ranges": stored_ranges,
        "parameters": {
            "algorithms": {
                "crc16-reflected": {
                    "polynomial": 0x8005,
                    "reflected_polynomial": 0xA001,
                    "reflect_input": True,
                    "reflect_output": False,
                    "xor_out": 0,
                    "byte_order": "low-to-high",
                    "record_endianness": "little",
                    "descriptor_end": "inclusive",
                },
                "additive32-le16-word-sum": {
                    "accumulator_bits": 32,
                    "word_bits": 16,
                    "word_endianness": "little",
                    "record_endianness": "little",
                    "address_mask": MS43_ADDRESS_MASK,
                    "descriptor_end": "exclusive",
                },
            },
            "image_size": MS43_IMAGE_SIZE,
            "osid": {
                "offset": MS43_OSID_OFFSET,
                "ascii": MS43_OSID.decode("ascii"),
            },
            "additive_metadata": {
                "offset": MS43_ADDITIVE_METADATA_OFFSET,
                "length": len(bytes.fromhex(MS43_ADDITIVE_METADATA_HEX)),
                "expected_hex": MS43_ADDITIVE_METADATA_HEX,
                "sha256": MS43_ADDITIVE_METADATA_SHA256,
            },
            "program_descriptor_file_delta": -0x80000,
            # Calibration ADD32 storage (0x72FFC..0x72FFF) is covered by the
            # calibration CRC.  Putting both additive records first provides
            # one conservative global order; only cal-ADD-before-cal-CRC is a
            # coverage dependency.
            "repair_order": [
                "program-additive32",
                "calibration-additive32",
                "boot",
                "prog",
                "cal",
            ],
            "scope": (
                "boot/program/calibration CRC16 plus program/calibration "
                "additive32 monitors"
            ),
            "records": records,
        },
    }


MS43_ALL_CHECKSUMS_CONTRACT = _build_ms43_all_checksums_contract()


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


def _require_exact_named_contract(
    context: Mapping[str, Any], expected: Mapping[str, Any], profile_id: str
) -> None:
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

    requested = {
        "profile": context["profile"],
        "covered_ranges": context["covered_ranges"],
        "stored_ranges": context["stored_ranges"],
        "parameters": context["parameters"],
    }
    if _canonical_json(requested) != _canonical_json(expected):
        raise ChecksumProfileError(
            f"requested checksum contract does not exactly match trusted profile {profile_id!r}"
        )


def _require_exact_contract(context: Mapping[str, Any]) -> None:
    _require_exact_named_contract(context, _build_contract(), PROFILE_ID)


def _require_exact_vy_contract(context: Mapping[str, Any]) -> None:
    _require_exact_named_contract(context, _build_vy_contract(), VY_PROFILE_ID)


def _require_exact_ms43_contract(context: Mapping[str, Any]) -> None:
    _require_exact_named_contract(context, _build_ms43_contract(), MS43_PROFILE_ID)


def _require_exact_ms43_all_checksums_contract(context: Mapping[str, Any]) -> None:
    _require_exact_named_contract(
        context,
        _build_ms43_all_checksums_contract(),
        MS43_ALL_CHECKSUMS_PROFILE_ID,
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


def _parse_and_validate_ms43_record(
    image: bytes, record: Mapping[str, Any]
) -> tuple[int, list[tuple[int, int]]]:
    offset = record["offset"]
    stored = int.from_bytes(image[offset:offset + 2], "little")
    count = int.from_bytes(image[offset + 2:offset + 4], "little")
    expected_descriptors = list(record["descriptor_segments"])
    if count != len(expected_descriptors):
        raise ChecksumProfileError(
            f"MS43 {record['name']} descriptor count mismatch at 0x{offset:05X}: "
            f"expected {len(expected_descriptors)}, got {count}"
        )

    descriptors = []
    cursor = offset + 4
    for _ in range(count):
        start = int.from_bytes(image[cursor:cursor + 4], "little")
        end = int.from_bytes(image[cursor + 4:cursor + 8], "little")
        cursor += 8
        if start > end:
            raise ChecksumProfileError(
                f"MS43 {record['name']} has reversed descriptor "
                f"0x{start:05X}..0x{end:05X}"
            )
        descriptors.append((start, end))

    if descriptors != expected_descriptors:
        got = ", ".join(f"0x{start:05X}..0x{end:05X}" for start, end in descriptors)
        wanted = ", ".join(
            f"0x{start:05X}..0x{end:05X}" for start, end in expected_descriptors
        )
        raise ChecksumProfileError(
            f"MS43 {record['name']} descriptor mismatch at 0x{offset:05X}; "
            f"expected {wanted}, got {got}"
        )
    return stored, descriptors


def verify_bmw_ms43_430069_crc16(
    image: bytes, context: Mapping[str, Any]
) -> dict[str, Any]:
    """Verify exact MS43 430069 CRC16 records; additive monitors are out of scope."""
    _require_exact_ms43_contract(context)
    if not isinstance(image, (bytes, bytearray, memoryview)):
        raise ChecksumProfileError("image must be bytes-like")
    image = bytes(image)
    if len(image) != MS43_IMAGE_SIZE:
        raise ChecksumProfileError(
            f"expected {MS43_IMAGE_SIZE}-byte MS43 full image, got {len(image)} bytes"
        )
    actual_osid = image[MS43_OSID_OFFSET:MS43_OSID_OFFSET + len(MS43_OSID)]
    if actual_osid != MS43_OSID:
        shown = actual_osid.decode("ascii", errors="replace")
        raise ChecksumProfileError(
            f"unsupported MS43 OSID {shown!r} at 0x{MS43_OSID_OFFSET:05X}; "
            "expected '430069'"
        )

    details = []
    all_valid = True
    for record in _MS43_RECORDS:
        stored, descriptor_segments = _parse_and_validate_ms43_record(image, record)
        computed = record["seed"]
        for start, end in record["file_segments"]:
            if start > end or end >= len(image):
                raise ChecksumProfileError(
                    f"MS43 {record['name']} mapped file range is invalid: "
                    f"0x{start:05X}..0x{end:05X}"
                )
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
                "descriptor_segments": [
                    {"start": start, "end": end, "length": end - start + 1}
                    for start, end in descriptor_segments
                ],
                "file_segments": [
                    {"start": start, "end": end, "length": end - start + 1}
                    for start, end in record["file_segments"]
                ],
            }
        )

    return {
        "valid": all_valid,
        "profile": MS43_PROFILE_ID,
        "scope": "boot/program/calibration CRC16 records only",
        "excluded_checksum_layers": [
            {"name": "program additive monitor", "offset": 0x6FDAE},
            {"name": "calibration additive monitor", "offset": 0x72FFC},
        ],
        "image_size": len(image),
        "osid": {
            "offset": MS43_OSID_OFFSET,
            "ascii": MS43_OSID.decode("ascii"),
            "matched": True,
        },
        "records": details,
    }


def _parse_and_validate_ms43_additive_record(
    image: bytes, record: Mapping[str, Any]
) -> tuple[int, int, list[tuple[int, int]], list[tuple[int, int]]]:
    stored_offset = record["offset"]
    stored = int.from_bytes(image[stored_offset:stored_offset + 4], "little")
    seed_offset = record["seed_offset"]
    seed = int.from_bytes(image[seed_offset:seed_offset + 4], "little")
    if seed != record["seed"]:
        raise ChecksumProfileError(
            f"MS43 {record['name']} seed mismatch at 0x{seed_offset:05X}: "
            f"expected 0x{record['seed']:08X}, got 0x{seed:08X}"
        )

    descriptor_count = record["descriptor_count"]
    if descriptor_count != 2:
        raise ChecksumProfileError(
            f"MS43 {record['name']} trusted descriptor count must be exactly 2"
        )
    cursor = record["descriptor_base"] + record["range_descriptor_offset"]
    descriptors = []
    for _ in range(descriptor_count):
        start = int.from_bytes(image[cursor:cursor + 4], "little")
        end = int.from_bytes(image[cursor + 4:cursor + 8], "little")
        cursor += 8
        if start >= end:
            raise ChecksumProfileError(
                f"MS43 {record['name']} has invalid half-open descriptor "
                f"[0x{start:05X},0x{end:05X})"
            )
        descriptors.append((start, end))

    expected_descriptors = list(record["descriptor_segments"])
    if descriptors != expected_descriptors:
        got = ", ".join(
            f"[0x{start:05X},0x{end:05X})" for start, end in descriptors
        )
        wanted = ", ".join(
            f"[0x{start:05X},0x{end:05X})"
            for start, end in expected_descriptors
        )
        raise ChecksumProfileError(
            f"MS43 {record['name']} descriptor mismatch; expected {wanted}, got {got}"
        )

    file_segments = [
        (start & MS43_ADDRESS_MASK, end & MS43_ADDRESS_MASK)
        for start, end in descriptors
    ]
    expected_file_segments = list(record["file_segments"])
    if file_segments != expected_file_segments:
        raise ChecksumProfileError(
            f"MS43 {record['name']} masked descriptor mapping differs from the "
            "trusted file ranges"
        )
    for start, end in file_segments:
        if start >= end or end > len(image) or start % 2 or end % 2:
            raise ChecksumProfileError(
                f"MS43 {record['name']} mapped word range is invalid: "
                f"[0x{start:05X},0x{end:05X})"
            )
    return stored, seed, descriptors, file_segments


def _ms43_additive32_le16_words(
    image: bytes, segments: list[tuple[int, int]], seed: int
) -> int:
    checksum = seed & 0xFFFFFFFF
    for start, end in segments:
        for offset in range(start, end, 2):
            checksum = (
                checksum + int.from_bytes(image[offset:offset + 2], "little")
            ) & 0xFFFFFFFF
    return checksum


def verify_bmw_ms43_430069_all_checksums(
    image: bytes, context: Mapping[str, Any]
) -> dict[str, Any]:
    """Verify all three CRC16 and both additive32 records without writes."""
    _require_exact_ms43_all_checksums_contract(context)
    if not isinstance(image, (bytes, bytearray, memoryview)):
        raise ChecksumProfileError("image must be bytes-like")
    image = bytes(image)
    if len(image) != MS43_IMAGE_SIZE:
        raise ChecksumProfileError(
            f"expected {MS43_IMAGE_SIZE}-byte MS43 full image, got {len(image)} bytes"
        )
    actual_osid = image[MS43_OSID_OFFSET:MS43_OSID_OFFSET + len(MS43_OSID)]
    if actual_osid != MS43_OSID:
        shown = actual_osid.decode("ascii", errors="replace")
        raise ChecksumProfileError(
            f"unsupported MS43 OSID {shown!r} at 0x{MS43_OSID_OFFSET:05X}; "
            "expected '430069'"
        )

    expected_metadata = bytes.fromhex(MS43_ADDITIVE_METADATA_HEX)
    metadata_end = MS43_ADDITIVE_METADATA_OFFSET + len(expected_metadata)
    actual_metadata = image[MS43_ADDITIVE_METADATA_OFFSET:metadata_end]
    actual_metadata_hash = hashlib.sha256(actual_metadata).hexdigest().upper()
    if actual_metadata != expected_metadata:
        raise ChecksumProfileError(
            "MS43 additive metadata mismatch at "
            f"0x{MS43_ADDITIVE_METADATA_OFFSET:05X}..0x{metadata_end - 1:05X}; "
            f"expected SHA-256 {MS43_ADDITIVE_METADATA_SHA256}, "
            f"got {actual_metadata_hash}"
        )

    details = []
    all_valid = True
    for record in _MS43_RECORDS:
        seed_offset = record["seed_offset"]
        seed = int.from_bytes(image[seed_offset:seed_offset + 2], "little")
        if seed != record["seed"]:
            raise ChecksumProfileError(
                f"MS43 {record['name']} seed mismatch at 0x{seed_offset:05X}: "
                f"expected 0x{record['seed']:04X}, got 0x{seed:04X}"
            )
        stored, descriptor_segments = _parse_and_validate_ms43_record(image, record)
        computed = seed
        for start, end in record["file_segments"]:
            if start > end or end >= len(image):
                raise ChecksumProfileError(
                    f"MS43 {record['name']} mapped file range is invalid: "
                    f"0x{start:05X}..0x{end:05X}"
                )
            computed = _crc16(image[start:end + 1], computed)
        valid = computed == stored
        all_valid = all_valid and valid
        details.append(
            {
                "name": record["name"],
                "algorithm": "crc16-reflected",
                "record_offset": record["offset"],
                "record_offset_hex": f"0x{record['offset']:05X}",
                "seed_offset": seed_offset,
                "seed_offset_hex": f"0x{seed_offset:05X}",
                "seed": seed,
                "seed_hex": f"0x{seed:04X}",
                "stored": stored,
                "stored_hex": f"0x{stored:04X}",
                "computed": computed,
                "computed_hex": f"0x{computed:04X}",
                "valid": valid,
                "descriptor_segments": [
                    {"start": start, "end": end, "length": end - start + 1}
                    for start, end in descriptor_segments
                ],
                "file_segments": [
                    {"start": start, "end": end, "length": end - start + 1}
                    for start, end in record["file_segments"]
                ],
            }
        )

    for record in _MS43_ADDITIVE_RECORDS:
        stored, seed, descriptors, file_segments = (
            _parse_and_validate_ms43_additive_record(image, record)
        )
        computed = _ms43_additive32_le16_words(image, file_segments, seed)
        valid = computed == stored
        all_valid = all_valid and valid
        details.append(
            {
                "name": record["name"],
                "algorithm": "additive32-le16-word-sum",
                "record_offset": record["offset"],
                "record_offset_hex": f"0x{record['offset']:05X}",
                "seed_offset": record["seed_offset"],
                "seed_offset_hex": f"0x{record['seed_offset']:05X}",
                "seed": seed,
                "seed_hex": f"0x{seed:08X}",
                "stored": stored,
                "stored_hex": f"0x{stored:08X}",
                "computed": computed,
                "computed_hex": f"0x{computed:08X}",
                "valid": valid,
                "descriptor_segments": [
                    {"start": start, "end": end, "length": end - start}
                    for start, end in descriptors
                ],
                "file_segments": [
                    {"start": start, "end": end, "length": end - start}
                    for start, end in file_segments
                ],
            }
        )

    return {
        "valid": all_valid,
        "profile": MS43_ALL_CHECKSUMS_PROFILE_ID,
        "scope": (
            "boot/program/calibration CRC16 plus program/calibration "
            "additive32 monitors"
        ),
        "image_size": len(image),
        "osid": {
            "offset": MS43_OSID_OFFSET,
            "ascii": MS43_OSID.decode("ascii"),
            "matched": True,
        },
        "additive_metadata": {
            "offset": MS43_ADDITIVE_METADATA_OFFSET,
            "length": len(actual_metadata),
            "sha256": actual_metadata_hash,
            "matched": True,
        },
        "repair_order": [
            "program-additive32",
            "calibration-additive32",
            "boot",
            "prog",
            "cal",
        ],
        "records": details,
    }


def verify_holden_vy_060a_92118883_additive16(
    image: bytes, context: Mapping[str, Any]
) -> dict[str, Any]:
    """Verify the exact 128 KiB VY $060A whole-file checksum without writes."""
    _require_exact_vy_contract(context)
    if not isinstance(image, (bytes, bytearray, memoryview)):
        raise ChecksumProfileError("image must be bytes-like")
    image = bytes(image)
    if len(image) != VY_IMAGE_SIZE:
        raise ChecksumProfileError(
            f"expected {VY_IMAGE_SIZE}-byte VY full image, got {len(image)} bytes"
        )

    actual_osid = int.from_bytes(
        image[VY_OSID_OFFSET:VY_OSID_OFFSET + 4], "big"
    )
    if actual_osid != VY_OSID:
        raise ChecksumProfileError(
            f"unsupported VY OSID {actual_osid} (0x{actual_osid:08X}) at "
            f"0x{VY_OSID_OFFSET:05X}; expected {VY_OSID} (0x{VY_OSID:08X})"
        )
    actual_program_id = image[VY_PROGRAM_ID_OFFSET]
    if actual_program_id != VY_PROGRAM_ID_BYTE:
        raise ChecksumProfileError(
            f"unsupported VY checksum-gate byte 0x{actual_program_id:02X} at "
            f"0x{VY_PROGRAM_ID_OFFSET:05X}; expected bypass marker 0xAA"
        )

    stored = int.from_bytes(
        image[VY_CHECKSUM_OFFSET:VY_CHECKSUM_OFFSET + 2], "big"
    )
    computed = (
        sum(image[VY_CHECKSUM_START:VY_CHECKSUM_SKIP_START])
        + sum(image[VY_CHECKSUM_SKIP_END:VY_CHECKSUM_END])
    ) & 0xFFFF
    segments = [
        {
            "start": VY_CHECKSUM_START,
            "end": VY_CHECKSUM_SKIP_START - 1,
            "length": VY_CHECKSUM_SKIP_START - VY_CHECKSUM_START,
        },
        {
            "start": VY_CHECKSUM_SKIP_END,
            "end": VY_CHECKSUM_END - 1,
            "length": VY_CHECKSUM_END - VY_CHECKSUM_SKIP_END,
        },
    ]
    return {
        "valid": stored == computed,
        "profile": VY_PROFILE_ID,
        "image_size": len(image),
        "osid": {
            "offset": VY_OSID_OFFSET,
            "value": actual_osid,
            "hex": f"0x{actual_osid:08X}",
            "matched": True,
        },
        "ecu_checksum_gate": {
            "offset": VY_PROGRAM_ID_OFFSET,
            "value": actual_program_id,
            "hex": f"0x{actual_program_id:02X}",
            "state": "bypass",
            "matched": True,
        },
        "records": [
            {
                "name": "whole-file",
                "record_offset": VY_CHECKSUM_OFFSET,
                "record_offset_hex": f"0x{VY_CHECKSUM_OFFSET:05X}",
                "stored": stored,
                "stored_hex": f"0x{stored:04X}",
                "computed": computed,
                "computed_hex": f"0x{computed:04X}",
                "valid": stored == computed,
                "segments": segments,
                "excluded": {
                    "start": VY_CHECKSUM_SKIP_START,
                    "end": VY_CHECKSUM_SKIP_END - 1,
                    "length": VY_CHECKSUM_SKIP_END - VY_CHECKSUM_SKIP_START,
                },
            }
        ],
    }


TRUSTED_CHECKSUM_VERIFIERS = {
    PROFILE_ID: verify_bmw_ms42_0110c6_crc16,
    MS43_PROFILE_ID: verify_bmw_ms43_430069_crc16,
    MS43_ALL_CHECKSUMS_PROFILE_ID: verify_bmw_ms43_430069_all_checksums,
    VY_PROFILE_ID: verify_holden_vy_060a_92118883_additive16,
}


__all__ = [
    "CHECKSUM_CONTRACT",
    "ChecksumProfileError",
    "IMAGE_SIZE",
    "MS43_ADDITIVE_METADATA_HEX",
    "MS43_ADDITIVE_METADATA_OFFSET",
    "MS43_ADDITIVE_METADATA_SHA256",
    "MS43_ADDRESS_MASK",
    "MS43_ALL_CHECKSUMS_CONTRACT",
    "MS43_ALL_CHECKSUMS_PROFILE_ID",
    "MS43_CHECKSUM_CONTRACT",
    "MS43_IMAGE_SIZE",
    "MS43_OSID",
    "MS43_OSID_OFFSET",
    "MS43_PROFILE_ID",
    "OSID_OFFSET",
    "PROFILE_ID",
    "TRUSTED_CHECKSUM_VERIFIERS",
    "VY_CHECKSUM_CONTRACT",
    "VY_CHECKSUM_END",
    "VY_CHECKSUM_OFFSET",
    "VY_CHECKSUM_SKIP_END",
    "VY_CHECKSUM_SKIP_START",
    "VY_CHECKSUM_START",
    "VY_IMAGE_SIZE",
    "VY_OSID",
    "VY_OSID_OFFSET",
    "VY_PROFILE_ID",
    "VY_PROGRAM_ID_BYTE",
    "VY_PROGRAM_ID_OFFSET",
    "verify_bmw_ms42_0110c6_crc16",
    "verify_bmw_ms43_430069_all_checksums",
    "verify_bmw_ms43_430069_crc16",
    "verify_holden_vy_060a_92118883_additive16",
]

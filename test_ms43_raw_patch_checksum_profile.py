"""Portable and pinned tests for the MS43 430069 CRC16-only profile."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from raw_patch_checksum_profiles import (
    ChecksumProfileError,
    MS43_CHECKSUM_CONTRACT,
    MS43_IMAGE_SIZE,
    MS43_OSID,
    MS43_OSID_OFFSET,
    MS43_PROFILE_ID,
    TRUSTED_CHECKSUM_VERIFIERS,
    verify_bmw_ms43_430069_crc16,
)


WORKSPACE = Path(__file__).resolve().parent.parent
VALID_PATH = (
    WORKSPACE
    / "1bmw_ms42_tuning_guides"
    / "all_ms42_bins"
    / "Siemens_MS43_MS430069_E46_M54B25_EU4_LHD.bin"
)
STALE_PORT_PATH = (
    WORKSPACE
    / "1bmw_ms42_tuning_guides"
    / "all_ms42_bins"
    / "Siemens_MS43_MS430069_E39_M54B25_EU4_LHD.bin"
)


def _context():
    context = copy.deepcopy(MS43_CHECKSUM_CONTRACT)
    context["phase"] = "input"
    return context


def _reference_crc16(data: bytes, seed: int) -> int:
    crc = seed & 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def _synthetic_valid_image() -> bytes:
    image = bytearray((index * 41 + 19) & 0xFF for index in range(MS43_IMAGE_SIZE))
    image[MS43_OSID_OFFSET:MS43_OSID_OFFSET + 6] = MS43_OSID
    records = MS43_CHECKSUM_CONTRACT["parameters"]["records"]
    for record in records:
        offset = record["offset"]
        descriptors = record["descriptor_segments"]
        image[offset + 2:offset + 4] = len(descriptors).to_bytes(2, "little")
        cursor = offset + 4
        for segment in descriptors:
            image[cursor:cursor + 4] = segment["start"].to_bytes(4, "little")
            image[cursor + 4:cursor + 8] = segment["end"].to_bytes(4, "little")
            cursor += 8
    for record in records:
        computed = record["seed"]
        for segment in record["file_segments"]:
            computed = _reference_crc16(
                image[segment["start"]:segment["end"] + 1], computed
            )
        image[record["offset"]:record["offset"] + 2] = computed.to_bytes(2, "little")
    return bytes(image)


def _load_pinned(path: Path, sha256: str) -> bytes:
    if not path.is_file():
        pytest.skip(f"workspace integration fixture is unavailable: {path}")
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest().upper() == sha256
    return data


def _by_name(result):
    return {record["name"]: record for record in result["records"]}


def test_registry_exports_ms43_profile():
    assert (
        TRUSTED_CHECKSUM_VERIFIERS[MS43_PROFILE_ID]
        is verify_bmw_ms43_430069_crc16
    )


def test_portable_synthetic_image_passes():
    result = verify_bmw_ms43_430069_crc16(_synthetic_valid_image(), _context())
    assert result["valid"] is True
    assert result["scope"] == "boot/program/calibration CRC16 records only"
    assert [item["offset"] for item in result["excluded_checksum_layers"]] == [
        0x6FDAE,
        0x72FFC,
    ]
    assert all(record["valid"] for record in result["records"])


def test_pinned_clean_430069_image_passes_all_crc_records():
    image = _load_pinned(
        VALID_PATH,
        "0F97B32F0C5AD517F8834E33F909BEAC6771764F0AC79A12569344BDA3F4443D",
    )
    result = verify_bmw_ms43_430069_crc16(image, _context())
    records = _by_name(result)
    assert result["valid"] is True
    assert records["boot"]["stored_hex"] == "0xC6D5"
    assert records["prog"]["stored_hex"] == "0x727E"
    assert records["cal"]["stored_hex"] == "0x5ADF"
    assert sum(item["length"] for item in records["prog"]["file_segments"]) == 365946


def test_known_stale_e39_port_is_rejected():
    image = _load_pinned(
        STALE_PORT_PATH,
        "200BFBA44A41A6CDB1B46ED39A922860C8ECE334D2090633EB2C9EA8AE3C8CBD",
    )
    result = verify_bmw_ms43_430069_crc16(image, _context())
    records = _by_name(result)
    assert result["valid"] is False
    assert records["boot"]["valid"] is True
    assert records["prog"]["valid"] is True
    assert records["cal"]["stored_hex"] == "0x5ADF"
    assert records["cal"]["computed_hex"] == "0xC138"


def test_covered_program_corruption_is_detected():
    corrupt = bytearray(_synthetic_valid_image())
    corrupt[0x2A3F3] ^= 0x01
    result = verify_bmw_ms43_430069_crc16(corrupt, _context())
    assert result["valid"] is False
    assert _by_name(result)["prog"]["valid"] is False


def test_descriptor_and_osid_drift_fail_closed():
    descriptor = bytearray(_synthetic_valid_image())
    descriptor[0x6FDE4] ^= 0x01
    with pytest.raises(ChecksumProfileError, match="MS43 prog descriptor mismatch"):
        verify_bmw_ms43_430069_crc16(descriptor, _context())

    osid = bytearray(_synthetic_valid_image())
    osid[MS43_OSID_OFFSET] = ord("X")
    with pytest.raises(ChecksumProfileError, match="unsupported MS43 OSID"):
        verify_bmw_ms43_430069_crc16(osid, _context())


@pytest.mark.parametrize("fault", ["covered", "stored", "seed", "mapping", "profile"])
def test_contract_drift_fails_closed(fault):
    context = _context()
    if fault == "covered":
        context["covered_ranges"][0]["length"] += 1
    elif fault == "stored":
        context["stored_ranges"][1]["offset"] += 1
    elif fault == "seed":
        context["parameters"]["records"][1]["seed"] ^= 1
    elif fault == "mapping":
        context["parameters"]["program_descriptor_file_delta"] += 1
    else:
        context["profile"] = "bmw-ms43-430056-crc16-v1"
    with pytest.raises(ChecksumProfileError, match="does not exactly match"):
        verify_bmw_ms43_430069_crc16(_synthetic_valid_image(), context)

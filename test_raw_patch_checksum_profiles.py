"""Tests for trusted built-in raw-patch checksum profiles."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from raw_patch_checksum_profiles import (
    CHECKSUM_CONTRACT,
    ChecksumProfileError,
    IMAGE_SIZE,
    MS43_PROFILE_ID,
    OSID_OFFSET,
    PROFILE_ID,
    TRUSTED_CHECKSUM_VERIFIERS,
    VY_PROFILE_ID,
    verify_bmw_ms42_0110c6_crc16,
)


WORKSPACE = Path(__file__).resolve().parent.parent
PARENT_PATH = (
    WORKSPACE
    / "1bmw_ms42_tuning_guides"
    / "all_ms42_bins"
    / "Siemens_MS42_0110C6_E46_M52TUB28_EU3_RHD (1).bin"
)
DS2_PATH = (
    WORKSPACE
    / "1bmw_ms42_tuning_guides"
    / "_ai_work"
    / "ms42_0110c6_ds2_logging_patch_20260920"
    / "MS42_0110C6_M52TUB28_EU3_RHD_DS2_0B_B0_LOGGING_PATCH_STATIC_PROOF_CHECKSUM_VALID_BENCH_ONLY_DO_NOT_FLASH.bin"
)


def _load_pinned(path: Path, sha256: str) -> bytes:
    if not path.is_file():
        pytest.skip(f"workspace integration fixture is unavailable: {path}")
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest().upper() == sha256
    return data


@pytest.fixture
def parent_image() -> bytes:
    return _load_pinned(
        PARENT_PATH,
        "65C3B91A05A0D6AE40F82E39F327FDC2FF672F9B61E2C3233780535E44539F90",
    )


@pytest.fixture
def ds2_image() -> bytes:
    return _load_pinned(
        DS2_PATH,
        "AF72CCEB84CF12D75A8791051A43BCE00F4CC33447ECF51C3B1B2625810ED9DD",
    )


def _context():
    context = copy.deepcopy(CHECKSUM_CONTRACT)
    context["phase"] = "input"
    return context


def _by_name(result):
    return {record["name"]: record for record in result["records"]}


def _reference_crc16(data: bytes, seed: int) -> int:
    """Independent bitwise reference for the reflected 0x8005 profile."""
    crc = seed & 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def _synthetic_valid_image() -> bytes:
    """Build a portable valid image without relying on private firmware bytes."""
    image = bytearray((index * 37 + 11) & 0xFF for index in range(IMAGE_SIZE))
    image[OSID_OFFSET:OSID_OFFSET + 6] = b"0110C6"
    records = CHECKSUM_CONTRACT["parameters"]["records"]

    for record in records:
        offset = record["offset"]
        segments = record["segments"]
        image[offset + 2:offset + 4] = len(segments).to_bytes(2, "little")
        cursor = offset + 4
        for segment in segments:
            image[cursor:cursor + 4] = segment["start"].to_bytes(4, "little")
            image[cursor + 4:cursor + 8] = segment["end"].to_bytes(4, "little")
            cursor += 8

    for record in records:
        computed = record["seed"]
        for segment in record["segments"]:
            computed = _reference_crc16(
                image[segment["start"]:segment["end"] + 1], computed
            )
        offset = record["offset"]
        image[offset:offset + 2] = computed.to_bytes(2, "little")
    return bytes(image)


def test_registry_exports_the_exact_trusted_profile():
    assert set(TRUSTED_CHECKSUM_VERIFIERS) == {
        PROFILE_ID,
        MS43_PROFILE_ID,
        VY_PROFILE_ID,
    }
    assert TRUSTED_CHECKSUM_VERIFIERS[PROFILE_ID] is verify_bmw_ms42_0110c6_crc16


def test_clean_parent_passes_all_exact_records(parent_image):
    result = verify_bmw_ms42_0110c6_crc16(parent_image, _context())

    assert result["valid"] is True
    records = _by_name(result)
    assert records["boot"]["stored_hex"] == "0xDF13"
    assert records["cal"]["stored_hex"] == "0x6143"
    assert records["prog"]["stored_hex"] == "0xF347"
    assert all(record["valid"] for record in result["records"])


def test_checksum_valid_ds2_artifact_passes(ds2_image):
    result = verify_bmw_ms42_0110c6_crc16(ds2_image, _context())

    assert result["valid"] is True
    assert _by_name(result)["prog"]["stored_hex"] == "0xAF88"


def test_corrupt_covered_byte_returns_invalid_record(parent_image):
    corrupt = bytearray(parent_image)
    corrupt[0x00100] ^= 0x01

    result = verify_bmw_ms42_0110c6_crc16(corrupt, _context())

    assert result["valid"] is False
    assert _by_name(result)["boot"]["valid"] is False
    assert _by_name(result)["cal"]["valid"] is True
    assert _by_name(result)["prog"]["valid"] is True


def test_corrupt_stored_checksum_returns_invalid_record(parent_image):
    corrupt = bytearray(parent_image)
    corrupt[0x50306] ^= 0x01

    result = verify_bmw_ms42_0110c6_crc16(corrupt, _context())

    assert result["valid"] is False
    assert _by_name(result)["prog"]["valid"] is False


def test_corrupt_descriptor_fails_closed(parent_image):
    corrupt = bytearray(parent_image)
    corrupt[0x5030A] ^= 0x01  # first program descriptor start address

    with pytest.raises(ChecksumProfileError, match="prog descriptor mismatch"):
        verify_bmw_ms42_0110c6_crc16(corrupt, _context())


def test_wrong_osid_fails_closed(parent_image):
    corrupt = bytearray(parent_image)
    corrupt[0x48008] = ord("X")

    with pytest.raises(ChecksumProfileError, match="unsupported MS42 OSID"):
        verify_bmw_ms42_0110c6_crc16(corrupt, _context())


@pytest.mark.parametrize("fault", ["covered", "stored", "seed", "record-offset", "profile"])
def test_any_checksum_contract_drift_fails_closed(parent_image, fault):
    context = _context()
    if fault == "covered":
        context["covered_ranges"][0]["length"] += 1
    elif fault == "stored":
        context["stored_ranges"][2]["offset"] += 1
    elif fault == "seed":
        context["parameters"]["records"][1]["seed"] ^= 1
    elif fault == "record-offset":
        context["parameters"]["records"][0]["offset"] += 1
    else:
        context["profile"] = "bmw-ms42-0110ca-crc16-v1"

    with pytest.raises(ChecksumProfileError, match="does not exactly match"):
        verify_bmw_ms42_0110c6_crc16(parent_image, context)


def test_payload_only_corruption_outside_ecu_crc_still_passes(ds2_image):
    corrupt = bytearray(ds2_image)
    corrupt[0x60E00] ^= 0x01
    assert hashlib.sha256(corrupt).digest() != hashlib.sha256(ds2_image).digest()
    assert not any(
        item["offset"] <= 0x60E00 < item["offset"] + item["length"]
        for item in CHECKSUM_CONTRACT["covered_ranges"]
    )

    result = verify_bmw_ms42_0110c6_crc16(corrupt, _context())

    assert result["valid"] is True
    assert all(record["valid"] for record in result["records"])


def test_portable_synthetic_image_passes_without_workspace_fixtures():
    result = verify_bmw_ms42_0110c6_crc16(_synthetic_valid_image(), _context())
    assert result["valid"] is True
    assert all(record["valid"] for record in result["records"])


def test_portable_synthetic_covered_corruption_is_detected():
    corrupt = bytearray(_synthetic_valid_image())
    corrupt[0x100] ^= 0x01
    result = verify_bmw_ms42_0110c6_crc16(corrupt, _context())
    assert result["valid"] is False
    assert _by_name(result)["boot"]["valid"] is False


def test_portable_synthetic_descriptor_and_osid_drift_fail_closed():
    descriptor = bytearray(_synthetic_valid_image())
    descriptor[0x5030A] ^= 0x01
    with pytest.raises(ChecksumProfileError, match="prog descriptor mismatch"):
        verify_bmw_ms42_0110c6_crc16(descriptor, _context())

    osid = bytearray(_synthetic_valid_image())
    osid[OSID_OFFSET] = ord("X")
    with pytest.raises(ChecksumProfileError, match="unsupported MS42 OSID"):
        verify_bmw_ms42_0110c6_crc16(osid, _context())


def test_portable_synthetic_out_of_coverage_corruption_still_needs_full_hash():
    corrupt = bytearray(_synthetic_valid_image())
    corrupt[0x60E00] ^= 0x01
    result = verify_bmw_ms42_0110c6_crc16(corrupt, _context())
    assert result["valid"] is True


def test_portable_synthetic_contract_drift_fails_closed():
    context = _context()
    context["parameters"]["records"][2]["seed"] ^= 1
    with pytest.raises(ChecksumProfileError, match="does not exactly match"):
        verify_bmw_ms42_0110c6_crc16(_synthetic_valid_image(), context)

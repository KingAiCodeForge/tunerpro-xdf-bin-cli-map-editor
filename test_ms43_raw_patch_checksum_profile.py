"""Portable and pinned tests for the MS43 430069 checksum profiles."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from raw_patch_checksum_profiles import (
    ChecksumProfileError,
    MS43_ADDITIVE_METADATA_HEX,
    MS43_ADDITIVE_METADATA_OFFSET,
    MS43_ADDITIVE_METADATA_SHA256,
    MS43_ALL_CHECKSUMS_CONTRACT,
    MS43_ALL_CHECKSUMS_PROFILE_ID,
    MS43_CHECKSUM_CONTRACT,
    MS43_IMAGE_SIZE,
    MS43_OSID,
    MS43_OSID_OFFSET,
    MS43_PROFILE_ID,
    TRUSTED_CHECKSUM_VERIFIERS,
    verify_bmw_ms43_430069_all_checksums,
    verify_bmw_ms43_430069_crc16,
)


WORKSPACE = Path(__file__).resolve().parent.parent
VALID_PATH = (
    WORKSPACE
    / "1bmw_ms42_tuning_guides"
    / "all_ms43_bins"
    / "Siemens_MS43_MS430069_E46_M54B25_EU4_LHD.bin"
)
STALE_PORT_PATH = (
    WORKSPACE
    / "1bmw_ms42_tuning_guides"
    / "all_ms42_bins"
    / "Siemens_MS43_MS430069_E39_M54B25_EU4_LHD.bin"
)
MS43_PARENT_SHA256 = (
    "0F97B32F0C5AD517F8834E33F909BEAC6771764F0AC79A12569344BDA3F4443D"
)
MS43_CRUISE_PATCHED_SHA256 = (
    "C2C2D890F54E9AF8F49B4110B6C0F19152D5F3A0B755D4BCC5DE3B2DB955A007"
)
MS43_CRUISE_CHUNKS = (
    (0x2A3F2, "9A4E05D0", "9A0C0510"),
    (0x2C968, "8A4E0BD0", "8A0C0B10"),
    (0x6FDE0, "7E72", "F512"),
)


def _context():
    context = copy.deepcopy(MS43_CHECKSUM_CONTRACT)
    context["phase"] = "input"
    return context


def _all_checksums_context():
    context = copy.deepcopy(MS43_ALL_CHECKSUMS_CONTRACT)
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


def _reference_additive32_le16(
    data: bytes | bytearray, segments: list[dict], seed: int
) -> int:
    checksum = seed & 0xFFFFFFFF
    for segment in segments:
        for offset in range(segment["start"], segment["end"], 2):
            checksum = (
                checksum + int.from_bytes(data[offset:offset + 2], "little")
            ) & 0xFFFFFFFF
    return checksum


def _synthetic_all_checksums_valid_image() -> bytes:
    """Build all five records without using a private firmware fixture."""
    image = bytearray((index * 43 + 23) & 0xFF for index in range(MS43_IMAGE_SIZE))
    image[MS43_OSID_OFFSET:MS43_OSID_OFFSET + 6] = MS43_OSID
    metadata = bytes.fromhex(MS43_ADDITIVE_METADATA_HEX)
    assert hashlib.sha256(metadata).hexdigest().upper() == MS43_ADDITIVE_METADATA_SHA256
    image[
        MS43_ADDITIVE_METADATA_OFFSET:MS43_ADDITIVE_METADATA_OFFSET + len(metadata)
    ] = metadata

    records = MS43_ALL_CHECKSUMS_CONTRACT["parameters"]["records"]
    for record in records:
        if record["algorithm"] != "crc16-reflected":
            continue
        image[record["seed_offset"]:record["seed_offset"] + 2] = record[
            "seed"
        ].to_bytes(2, "little")
        offset = record["stored_offset"]
        descriptors = record["descriptor_segments"]
        image[offset + 2:offset + 4] = len(descriptors).to_bytes(2, "little")
        cursor = offset + 4
        for segment in descriptors:
            image[cursor:cursor + 4] = segment["start"].to_bytes(4, "little")
            image[cursor + 4:cursor + 8] = segment["end"].to_bytes(4, "little")
            cursor += 8

    # The calibration additive result is covered by the calibration CRC.  The
    # profile uses the conservative global order of both additive records first.
    for record in records:
        if record["algorithm"] != "additive32-le16-word-sum":
            continue
        computed = _reference_additive32_le16(
            image, record["file_segments"], record["seed"]
        )
        offset = record["stored_offset"]
        image[offset:offset + 4] = computed.to_bytes(4, "little")

    for record in records:
        if record["algorithm"] != "crc16-reflected":
            continue
        computed = record["seed"]
        for segment in record["file_segments"]:
            computed = _reference_crc16(
                image[segment["start"]:segment["end"] + 1], computed
            )
        offset = record["stored_offset"]
        image[offset:offset + 2] = computed.to_bytes(2, "little")
    return bytes(image)


def _apply_pinned_cruise_patch(image: bytes) -> bytes:
    patched = bytearray(image)
    for offset, expected_hex, replacement_hex in MS43_CRUISE_CHUNKS:
        expected = bytes.fromhex(expected_hex)
        replacement = bytes.fromhex(replacement_hex)
        assert patched[offset:offset + len(expected)] == expected
        patched[offset:offset + len(expected)] = replacement
    result = bytes(patched)
    assert hashlib.sha256(result).hexdigest().upper() == MS43_CRUISE_PATCHED_SHA256
    return result


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
    assert (
        TRUSTED_CHECKSUM_VERIFIERS[MS43_ALL_CHECKSUMS_PROFILE_ID]
        is verify_bmw_ms43_430069_all_checksums
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


def test_all_five_portable_synthetic_image_passes():
    result = verify_bmw_ms43_430069_all_checksums(
        _synthetic_all_checksums_valid_image(), _all_checksums_context()
    )
    assert result["valid"] is True
    assert result["additive_metadata"] == {
        "offset": 0x6FDB2,
        "length": 46,
        "sha256": MS43_ADDITIVE_METADATA_SHA256,
        "matched": True,
    }
    assert result["repair_order"][:2] == [
        "program-additive32",
        "calibration-additive32",
    ]
    assert set(_by_name(result)) == {
        "boot",
        "prog",
        "cal",
        "program-additive32",
        "calibration-additive32",
    }
    assert all(record["valid"] for record in result["records"])


def test_all_five_pinned_clean_and_cruise_patched_images_pass():
    clean = _load_pinned(VALID_PATH, MS43_PARENT_SHA256)
    patched = _apply_pinned_cruise_patch(clean)

    clean_result = verify_bmw_ms43_430069_all_checksums(
        clean, _all_checksums_context()
    )
    patched_result = verify_bmw_ms43_430069_all_checksums(
        patched, _all_checksums_context()
    )
    clean_records = _by_name(clean_result)
    patched_records = _by_name(patched_result)

    assert clean_result["valid"] is True
    assert patched_result["valid"] is True
    assert clean_records["boot"]["stored_hex"] == "0xC6D5"
    assert clean_records["prog"]["stored_hex"] == "0x727E"
    assert patched_records["prog"]["stored_hex"] == "0x12F5"
    assert clean_records["cal"]["stored_hex"] == "0x5ADF"
    assert patched_records["cal"]["stored_hex"] == "0x5ADF"
    assert clean_records["program-additive32"]["stored_hex"] == "0xB3DAAD17"
    assert patched_records["program-additive32"]["stored_hex"] == "0xB3DAAD17"
    assert clean_records["calibration-additive32"]["stored_hex"] == "0xA6202B49"
    assert patched_records["calibration-additive32"]["stored_hex"] == "0xA6202B49"
    assert clean_records["program-additive32"]["seed_offset"] == 0x6FDB2
    assert clean_records["calibration-additive32"]["seed_offset"] == 0x6FDB8


@pytest.mark.parametrize(
    ("offset", "invalid_records"),
    [
        (0x50000, {"prog", "program-additive32"}),
        (0x712C6, {"cal", "calibration-additive32"}),
    ],
)
def test_all_five_covered_corruption_detects_both_layers(offset, invalid_records):
    corrupt = bytearray(_synthetic_all_checksums_valid_image())
    corrupt[offset] ^= 0x01
    result = verify_bmw_ms43_430069_all_checksums(
        corrupt, _all_checksums_context()
    )
    assert result["valid"] is False
    records = _by_name(result)
    assert {name for name, record in records.items() if not record["valid"]} == (
        invalid_records
    )


def test_all_five_stored_additive_corruption_is_detected():
    program = bytearray(_synthetic_all_checksums_valid_image())
    program[0x6FDAE] ^= 0x01
    program_result = verify_bmw_ms43_430069_all_checksums(
        program, _all_checksums_context()
    )
    assert program_result["valid"] is False
    assert _by_name(program_result)["program-additive32"]["valid"] is False

    calibration = bytearray(_synthetic_all_checksums_valid_image())
    calibration[0x72FFC] ^= 0x01
    calibration_result = verify_bmw_ms43_430069_all_checksums(
        calibration, _all_checksums_context()
    )
    assert calibration_result["valid"] is False
    records = _by_name(calibration_result)
    assert records["calibration-additive32"]["valid"] is False
    assert records["cal"]["valid"] is False


@pytest.mark.parametrize(
    "offset",
    [0x6FDB2, 0x6FDB6, 0x6FDB8, 0x6FDBC, 0x6FDBE, 0x6FDDE],
)
def test_all_five_any_additive_metadata_drift_fails_closed(offset):
    corrupt = bytearray(_synthetic_all_checksums_valid_image())
    corrupt[offset] ^= 0x01
    with pytest.raises(ChecksumProfileError, match="additive metadata mismatch"):
        verify_bmw_ms43_430069_all_checksums(corrupt, _all_checksums_context())


def test_all_five_crc_seed_and_osid_drift_fail_closed():
    seed = bytearray(_synthetic_all_checksums_valid_image())
    seed[0x03FE6] ^= 0x01
    with pytest.raises(ChecksumProfileError, match="boot seed mismatch"):
        verify_bmw_ms43_430069_all_checksums(seed, _all_checksums_context())

    osid = bytearray(_synthetic_all_checksums_valid_image())
    osid[MS43_OSID_OFFSET] = ord("X")
    with pytest.raises(ChecksumProfileError, match="unsupported MS43 OSID"):
        verify_bmw_ms43_430069_all_checksums(osid, _all_checksums_context())


@pytest.mark.parametrize(
    "fault", ["covered", "stored", "seed-offset", "metadata", "order", "profile"]
)
def test_all_five_contract_drift_fails_closed(fault):
    context = _all_checksums_context()
    if fault == "covered":
        context["covered_ranges"][0]["length"] += 1
    elif fault == "stored":
        context["stored_ranges"][1]["length"] += 1
    elif fault == "seed-offset":
        context["parameters"]["records"][4]["seed_offset"] -= 6
    elif fault == "metadata":
        context["parameters"]["additive_metadata"]["expected_hex"] = "00"
    elif fault == "order":
        context["parameters"]["repair_order"].reverse()
    else:
        context["profile"] = "bmw-ms43-430069-four-checksums-v1"
    with pytest.raises(ChecksumProfileError, match="does not exactly match"):
        verify_bmw_ms43_430069_all_checksums(
            _synthetic_all_checksums_valid_image(), context
        )


def test_all_five_repair_order_requires_additive_before_calibration_crc():
    image = bytearray(_synthetic_all_checksums_valid_image())
    image[0x712C6] ^= 0x01
    records = {
        record["name"]: record
        for record in MS43_ALL_CHECKSUMS_CONTRACT["parameters"]["records"]
    }
    cal_crc = records["cal"]
    cal_add = records["calibration-additive32"]

    # Deliberately wrong: repair the covering CRC first, then mutate its input
    # by storing the repaired additive result.
    computed_crc = cal_crc["seed"]
    for segment in cal_crc["file_segments"]:
        computed_crc = _reference_crc16(
            image[segment["start"]:segment["end"] + 1], computed_crc
        )
    image[cal_crc["stored_offset"]:cal_crc["stored_offset"] + 2] = (
        computed_crc.to_bytes(2, "little")
    )
    computed_add = _reference_additive32_le16(
        image, cal_add["file_segments"], cal_add["seed"]
    )
    image[cal_add["stored_offset"]:cal_add["stored_offset"] + 4] = (
        computed_add.to_bytes(4, "little")
    )
    wrong_order = verify_bmw_ms43_430069_all_checksums(
        image, _all_checksums_context()
    )
    assert _by_name(wrong_order)["calibration-additive32"]["valid"] is True
    assert _by_name(wrong_order)["cal"]["valid"] is False

    # Correct order: store additive32, then recompute the CRC that covers it.
    computed_crc = cal_crc["seed"]
    for segment in cal_crc["file_segments"]:
        computed_crc = _reference_crc16(
            image[segment["start"]:segment["end"] + 1], computed_crc
        )
    image[cal_crc["stored_offset"]:cal_crc["stored_offset"] + 2] = (
        computed_crc.to_bytes(2, "little")
    )
    corrected = verify_bmw_ms43_430069_all_checksums(
        image, _all_checksums_context()
    )
    assert corrected["valid"] is True

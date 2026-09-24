"""Portable and pinned tests for the VY $060A trusted checksum profile."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest

from raw_patch_checksum_profiles import (
    ChecksumProfileError,
    TRUSTED_CHECKSUM_VERIFIERS,
    VY_CHECKSUM_CONTRACT,
    VY_CHECKSUM_OFFSET,
    VY_CHECKSUM_SKIP_START,
    VY_IMAGE_SIZE,
    VY_OSID,
    VY_OSID_OFFSET,
    VY_PROFILE_ID,
    VY_PROGRAM_ID_BYTE,
    VY_PROGRAM_ID_OFFSET,
    verify_holden_vy_060a_92118883_additive16,
)


WORKSPACE = Path(__file__).resolve().parent.parent
RAW_PARENT_PATH = (
    WORKSPACE
    / "kingaituning_orders_for_holdens"
    / "work"
    / "final_tune_examples_20260717"
    / "STOCK_BASES_AND_XDFS"
    / "VY_$060A"
    / "VX-VY_V6_$060A_Enhanced_v1.0a.bin"
)
CHECKSUM_CONTROL_PATH = (
    WORKSPACE
    / "VY_V6_Assembly_Modding"
    / "bin_patch_test"
    / "bench_pack_20260924_v1"
    / "00_v1.0a_checksum_control_BENCH_ONLY.bin"
)


def _context():
    context = copy.deepcopy(VY_CHECKSUM_CONTRACT)
    context["phase"] = "input"
    return context


def _reference_checksum(image: bytes | bytearray) -> int:
    return (
        sum(image[0x02000:0x04000]) + sum(image[0x04008:0x20000])
    ) & 0xFFFF


def _synthetic_valid_image() -> bytes:
    image = bytearray((index * 29 + 7) & 0xFF for index in range(VY_IMAGE_SIZE))
    image[VY_OSID_OFFSET:VY_OSID_OFFSET + 4] = VY_OSID.to_bytes(4, "big")
    image[VY_PROGRAM_ID_OFFSET] = VY_PROGRAM_ID_BYTE
    checksum = _reference_checksum(image)
    image[VY_CHECKSUM_OFFSET:VY_CHECKSUM_OFFSET + 2] = checksum.to_bytes(2, "big")
    return bytes(image)


def _load_pinned(path: Path, sha256: str) -> bytes:
    if not path.is_file():
        pytest.skip(f"workspace integration fixture is unavailable: {path}")
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest().upper() == sha256
    return data


def test_registry_exports_vy_profile():
    assert (
        TRUSTED_CHECKSUM_VERIFIERS[VY_PROFILE_ID]
        is verify_holden_vy_060a_92118883_additive16
    )


def test_portable_synthetic_image_passes():
    result = verify_holden_vy_060a_92118883_additive16(
        _synthetic_valid_image(), _context()
    )
    record = result["records"][0]
    assert result["valid"] is True
    assert record["stored"] == record["computed"]
    assert record["segments"] == [
        {"start": 0x02000, "end": 0x03FFF, "length": 0x02000},
        {"start": 0x04008, "end": 0x1FFFF, "length": 0x1BFF8},
    ]


def test_included_byte_corruption_is_detected():
    corrupt = bytearray(_synthetic_valid_image())
    corrupt[0x125BA] ^= 0x01
    result = verify_holden_vy_060a_92118883_additive16(corrupt, _context())
    assert result["valid"] is False


def test_excluded_non_checksum_corruption_needs_full_hash():
    clean = _synthetic_valid_image()
    corrupt = bytearray(clean)
    corrupt[VY_CHECKSUM_SKIP_START] ^= 0x01
    assert hashlib.sha256(corrupt).digest() != hashlib.sha256(clean).digest()
    result = verify_holden_vy_060a_92118883_additive16(corrupt, _context())
    assert result["valid"] is True


def test_stored_checksum_corruption_is_detected():
    corrupt = bytearray(_synthetic_valid_image())
    corrupt[VY_CHECKSUM_OFFSET] ^= 0x01
    result = verify_holden_vy_060a_92118883_additive16(corrupt, _context())
    assert result["valid"] is False


def test_wrong_osid_checksum_gate_and_size_fail_closed():
    wrong_osid = bytearray(_synthetic_valid_image())
    wrong_osid[VY_OSID_OFFSET] ^= 0x01
    with pytest.raises(ChecksumProfileError, match="unsupported VY OSID"):
        verify_holden_vy_060a_92118883_additive16(wrong_osid, _context())

    wrong_gate = bytearray(_synthetic_valid_image())
    wrong_gate[VY_PROGRAM_ID_OFFSET] = 0x06
    with pytest.raises(ChecksumProfileError, match="checksum-gate byte"):
        verify_holden_vy_060a_92118883_additive16(wrong_gate, _context())

    with pytest.raises(ChecksumProfileError, match="131072-byte VY full image"):
        verify_holden_vy_060a_92118883_additive16(b"\x00", _context())


@pytest.mark.parametrize("fault", ["covered", "stored", "algorithm", "osid", "profile"])
def test_contract_drift_fails_closed(fault):
    context = _context()
    if fault == "covered":
        context["covered_ranges"][0]["length"] += 1
    elif fault == "stored":
        context["stored_ranges"][0]["offset"] += 1
    elif fault == "algorithm":
        context["parameters"]["algorithm"] = "crc16"
    elif fault == "osid":
        context["parameters"]["osid"]["value"] += 1
    else:
        context["profile"] = "holden-vy-060b-additive16-bypass-aware-v1"

    with pytest.raises(ChecksumProfileError, match="does not exactly match"):
        verify_holden_vy_060a_92118883_additive16(
            _synthetic_valid_image(), context
        )


def test_pinned_download_is_stale_but_checksum_control_passes():
    raw = _load_pinned(
        RAW_PARENT_PATH,
        "5CB8BD1C61DA37A3846B6C28600CDC21DB3CEEF0C764232D0CD7EC8D6E836ABD",
    )
    control = _load_pinned(
        CHECKSUM_CONTROL_PATH,
        "34DFC79A76CDE89CA960D3D542BA5ECB572B91B10FF6B1C2A6C2836F16F58FFB",
    )

    raw_result = verify_holden_vy_060a_92118883_additive16(raw, _context())
    control_result = verify_holden_vy_060a_92118883_additive16(control, _context())

    assert raw_result["valid"] is False
    assert raw_result["records"][0]["stored_hex"] == "0x8E6F"
    assert raw_result["records"][0]["computed_hex"] == "0x9E9F"
    assert control_result["valid"] is True
    assert control_result["records"][0]["stored_hex"] == "0x9E9F"
    differences = [index for index, pair in enumerate(zip(raw, control)) if pair[0] != pair[1]]
    assert differences == [0x04006, 0x04007]

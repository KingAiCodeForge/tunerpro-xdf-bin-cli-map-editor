"""Portable synthetic-only tests for the opt-in VY checksum repair-copy adapter.

Uses repository's raw_patch_checksum_profiles as the trusted verifier when run
within KingAI CLI Map Editor; no real firmware is bundled or generated.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from checksum_repair_copy import (
    ChecksumRepairCopyError, plan_repair_copy, write_repair_package
)
from raw_patch_checksum_profiles import (
    VY_CHECKSUM_CONTRACT, VY_CHECKSUM_OFFSET, VY_PROGRAM_ID_OFFSET,
    VY_OSID, VY_OSID_OFFSET, VY_IMAGE_SIZE,
    verify_holden_vy_060a_92118883_additive16,
)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def reference_sum(img):
    # This is independent of the production adapter and verifier call path.
    return (sum(img[0x2000:0x4000]) + sum(img[0x4008:0x20000])) % 65536


def synthetic(*, stale=True):
    buf = bytearray((i*29+7)&255 for i in range(VY_IMAGE_SIZE))
    buf[VY_OSID_OFFSET:VY_OSID_OFFSET+4] = VY_OSID.to_bytes(4, 'big')
    buf[VY_PROGRAM_ID_OFFSET] = 0xAA
    wanted=reference_sum(buf)
    stored=wanted ^ (0x1234 if stale else 0)
    buf[VY_CHECKSUM_OFFSET:VY_CHECKSUM_OFFSET+2]=stored.to_bytes(2, 'big')
    return bytes(buf)


def test_repair_produces_exact_two_byte_checksum_copy():
    original=synthetic()
    result,receipt=plan_repair_copy(original,expected_sha256=sha(original))
    assert not receipt['before']['valid']
    assert receipt['after']['valid']
    assert receipt['gate']['state']=='bypass'
    assert receipt['gate']['ecu_checksum_enforcement_enabled'] is False
    assert set(int(o,16) for o in receipt['changed_offsets']) <= {0x4006,0x4007}
    assert len(receipt['changed_offsets']) == len(receipt['changed_bytes'])
    assert len(receipt['changed_offsets']) >= 1
    assert result[VY_PROGRAM_ID_OFFSET]==original[VY_PROGRAM_ID_OFFSET]==0xAA
    assert result[VY_OSID_OFFSET:VY_OSID_OFFSET+4]==original[VY_OSID_OFFSET:VY_OSID_OFFSET+4]
    assert int.from_bytes(result[0x4006:0x4008],'big') == reference_sum(original)
    assert verify_holden_vy_060a_92118883_additive16(
        result, dict(VY_CHECKSUM_CONTRACT, phase='output'))['valid']
    assert original[0x4006:0x4008] != result[0x4006:0x4008]
    assert receipt['source_sha256']==sha(original)
    assert receipt['output_sha256']==sha(result)


@pytest.mark.parametrize('offset', [0x2000,0x3fff,0x4008,0x7ffc,0x125ba,0x1ffff])
def test_independent_sum_tracks_covered_changes(offset):
    b=bytearray(synthetic(stale=False))
    b[offset]^=1
    if offset==0x4008:
        with pytest.raises(ChecksumRepairCopyError,match='gate'):
            plan_repair_copy(bytes(b),expected_sha256=sha(bytes(b)))
    elif VY_OSID_OFFSET <= offset < VY_OSID_OFFSET + 4:
        with pytest.raises(ChecksumRepairCopyError,match='OSID'):
            plan_repair_copy(bytes(b),expected_sha256=sha(bytes(b)))
    else:
        result,receipt=plan_repair_copy(bytes(b),expected_sha256=sha(bytes(b)))
        assert receipt['after']['valid']
        assert int.from_bytes(result[0x4006:0x4008],'big') == reference_sum(b)


def test_already_valid_returns_no_change_plan_and_refuses_copy(tmp_path):
    source=synthetic(stale=False)
    result,receipt=plan_repair_copy(source,expected_sha256=sha(source))
    assert result==source
    assert receipt['status']=='ALREADY_VALID_NO_WRITE'
    assert not receipt['changed_offsets']
    f=tmp_path/'clean.bin';f.write_bytes(source)
    with pytest.raises(ChecksumRepairCopyError,match='already valid'):
        write_repair_package(f,tmp_path/'fresh',expected_sha256=sha(source))
    assert not (tmp_path/'fresh').exists()


def test_wrong_sha_fails_before_repair():
    data=synthetic()
    with pytest.raises(ChecksumRepairCopyError,match='SHA-256 mismatch'):
        plan_repair_copy(data,expected_sha256='0'*64)


@pytest.mark.parametrize('bad', ['', 'x'*64, '123', None, '0'*65])
def test_invalid_sha_rejected(bad):
    with pytest.raises(ChecksumRepairCopyError,match='64 hex digits'):
        plan_repair_copy(synthetic(),expected_sha256=bad)


def test_wrong_osid_gate_and_size_refused_even_if_hash_approved():
    raw=bytearray(synthetic())
    raw[VY_OSID_OFFSET] ^=1
    with pytest.raises(ChecksumRepairCopyError,match='unsupported VY OSID'):
        plan_repair_copy(bytes(raw),expected_sha256=sha(raw))
    raw=bytearray(synthetic())
    raw[VY_PROGRAM_ID_OFFSET]=0x06
    with pytest.raises(ChecksumRepairCopyError,match='checksum-gate byte'):
        plan_repair_copy(bytes(raw),expected_sha256=sha(raw))
    raw=b'bad'
    with pytest.raises(ChecksumRepairCopyError,match='full image'):
        plan_repair_copy(raw,expected_sha256=sha(raw))


def test_reject_mutable_input():
    b=bytearray(synthetic())
    with pytest.raises(ChecksumRepairCopyError,match='immutable bytes'):
        plan_repair_copy(b,expected_sha256=sha(b))


def test_new_output_dir_receipt_readback_and_source_preserved(tmp_path):
    data=synthetic()
    src=tmp_path/'calibration.bin';src.write_bytes(data)
    d=tmp_path/'new_review'
    receipt=write_repair_package(src,d,expected_sha256=sha(data))
    repaired=(d/'calibration.checksum-copy.bin').read_bytes()
    from_disk=json.loads((d/'receipt.json').read_text())
    assert from_disk==receipt
    assert src.read_bytes()==data
    assert sha(repaired)==receipt['output_sha256']
    assert repaired[VY_PROGRAM_ID_OFFSET]==0xAA
    assert int.from_bytes(repaired[0x4006:0x4008],'big')==reference_sum(data)
    assert not any(path.suffix in {'.xdl','.adx','.xdf'} for path in d.iterdir())
    with pytest.raises(FileExistsError,match='already exists'):
        write_repair_package(src,d,expected_sha256=sha(data))
    assert (d/'calibration.checksum-copy.bin').read_bytes()==repaired


def test_preview_cli_never_writes_and_reports_copy_status(tmp_path):
    data=synthetic()
    f=tmp_path/'original.bin';f.write_bytes(data)
    c=subprocess.run([sys.executable,'-B','-m','checksum_repair_copy','--bin',str(f),
                      '--expected-sha256',sha(data)],cwd=Path(__file__).parent,
                     capture_output=True,text=True,check=False)
    assert c.returncode==0,c.stderr
    result=json.loads(c.stdout)
    assert result['status']=='REPAIR_TO_COPY_REVIEW_ONLY'
    assert sorted(x.name for x in tmp_path.iterdir())==['original.bin']


def test_cli_wrong_hash_exits_2_and_does_not_write(tmp_path):
    data=synthetic()
    f=tmp_path/'original.bin';f.write_bytes(data)
    c=subprocess.run([sys.executable,'-B','-m','checksum_repair_copy','--bin',str(f),
                      '--expected-sha256','0'*64,'--output-dir',str(tmp_path/'output')],
                     cwd=Path(__file__).parent,capture_output=True,text=True,check=False)
    assert c.returncode==2
    assert not (tmp_path/'output').exists()
    assert f.read_bytes()==data


def test_cli_output_dir_new_copy_and_no_overwrite(tmp_path):
    data=synthetic()
    f=tmp_path/'input.bin';f.write_bytes(data)
    dst=tmp_path/'target'
    cmd=[sys.executable,'-B','-m','checksum_repair_copy','--bin',str(f),
         '--expected-sha256',sha(data),'--output-dir',str(dst)]
    c=subprocess.run(cmd,cwd=Path(__file__).parent,capture_output=True,text=True,check=False)
    assert c.returncode==0,c.stderr
    assert (dst/'input.checksum-copy.bin').exists()
    assert json.loads(c.stdout)['status']=='REPAIR_TO_COPY_REVIEW_ONLY'
    again=subprocess.run(cmd,cwd=Path(__file__).parent,capture_output=True,text=True,check=False)
    assert again.returncode==2
    assert f.read_bytes()==data


def test_missing_parent_output_path_is_not_created(tmp_path):
    data=synthetic()
    f=tmp_path/'input.bin';f.write_bytes(data)
    bad=tmp_path/'absent'/'nested'
    with pytest.raises(ChecksumRepairCopyError,match='parent directory'):
        write_repair_package(f,bad,expected_sha256=sha(data))
    assert not bad.exists()


def test_source_missing_rejected_without_output(tmp_path):
    f=tmp_path/'missing.bin';out=tmp_path/'new'
    with pytest.raises(ChecksumRepairCopyError,match='existing file'):
        write_repair_package(f,out,expected_sha256='0'*64)
    assert not out.exists()


def test_repair_candidate_not_flash_approved():
    data=synthetic()
    _,receipt=plan_repair_copy(data,expected_sha256=sha(data))
    assert 'flash/readback' in receipt['not_qualified']
    assert 'firmware-execution' in receipt['not_qualified']
    assert not receipt['gate']['ecu_checksum_enforcement_enabled']


def test_portable_golden_stored_8e6f_repair_9e9f():
    """Synthetic golden record; not the proprietary Enhanced v1.0a image."""
    image = bytearray(VY_IMAGE_SIZE)
    osid = VY_OSID.to_bytes(4, 'big')
    image[VY_OSID_OFFSET:VY_OSID_OFFSET+4] = osid
    image[VY_PROGRAM_ID_OFFSET] = 0xAA
    remaining = (0x9E9F - sum(osid) - 0xAA) % 65536
    full, tail = divmod(remaining, 255)
    image[0x2000:0x2000+full] = bytes([255])*full
    if tail:
        image[0x2000+full] = tail
    image[VY_CHECKSUM_OFFSET:VY_CHECKSUM_OFFSET+2] = bytes.fromhex('8E6F')
    original = bytes(image)
    assert reference_sum(original) == 0x9E9F
    repaired, receipt = plan_repair_copy(original, expected_sha256=sha(original))
    assert original[0x4006:0x4008] == bytes.fromhex('8E6F')
    assert repaired[0x4006:0x4008] == bytes.fromhex('9E9F')
    assert receipt['changed_offsets'] == ['0x04006', '0x04007']
    assert receipt['before']['calculated_hex'] == '0x9E9F'
    assert receipt['after']['valid'] is True

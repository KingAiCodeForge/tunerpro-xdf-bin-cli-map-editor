"""Source-identity and byte-bounded plan snapshot contract tests."""
import hashlib
from pathlib import Path
import pytest
from batch_plan_snapshot import MAX_PLAN_BYTES, snapshot_plan


def test_hash_is_exact_snapshot_not_second_path_read(tmp_path):
    path = tmp_path / 'plan.json'
    payload = b'{"schema":"old"}\n'
    path.write_bytes(payload)
    snap, digest = snapshot_plan(path)
    path.write_bytes(b'{"schema":"new"}\n')
    assert snap == payload
    assert digest == hashlib.sha256(payload).hexdigest()
    assert hashlib.sha256(path.read_bytes()).hexdigest() != digest


@pytest.mark.parametrize('data', [b'type,map,value\nscalar,Fuel,10\n',
                                  b'\xef\xbb\xbf{"schema":"x"}\n',
                                  bytes(range(1, 64))])
def test_preserve_raw_bytes_without_normalising_line_endings(tmp_path, data):
    path = tmp_path / 'plan.csv'
    path.write_bytes(data)
    observed, digest = snapshot_plan(path)
    assert observed == data
    assert digest == hashlib.sha256(data).hexdigest()


def test_max_size_is_accepted(tmp_path):
    path = tmp_path / 'plan.csv'
    path.write_bytes(b'x' * 256)
    data, digest = snapshot_plan(path, limit=256)
    assert len(data) == 256


def test_one_byte_over_limit_is_rejected(tmp_path):
    path = tmp_path / 'plan.csv'
    path.write_bytes(b'x' * 257)
    with pytest.raises(ValueError, match='exceeds 256 byte limit'):
        snapshot_plan(path, limit=256)


@pytest.mark.parametrize('limit', [0, -1, True, 1.3, None])
def test_invalid_plan_limits_are_refused(tmp_path, limit):
    path = tmp_path / 'plan.csv'
    path.write_bytes(b'x')
    with pytest.raises(ValueError, match='positive integer'):
        snapshot_plan(path, limit=limit)


def test_empty_and_nul_plans_refused(tmp_path):
    path = tmp_path / 'plan.json'
    path.write_bytes(b'')
    with pytest.raises(ValueError, match='empty'):
        snapshot_plan(path)
    path.write_bytes(b'{"foo":"\x00"}')
    with pytest.raises(ValueError, match='NUL byte'):
        snapshot_plan(path)


def test_content_snapshot_cannot_change_after_original_file_mutates(tmp_path):
    path = tmp_path / 'plan.csv'
    path.write_bytes(b'type,map,value\r\nscalar,Map,1\r\n')
    snapshot, digest = snapshot_plan(path)
    path.unlink()
    path.write_bytes(b'type,map,value\nscalar,Map,2\n')
    assert snapshot.decode('utf-8').endswith('Map,1\r\n')
    assert hashlib.sha256(snapshot).hexdigest() == digest
    assert hashlib.sha256(path.read_bytes()).hexdigest() != digest


def test_default_limit_is_bounded_reasonably():
    assert MAX_PLAN_BYTES == 32 * 1024 * 1024

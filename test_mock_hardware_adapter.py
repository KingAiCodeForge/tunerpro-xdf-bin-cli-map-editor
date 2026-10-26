"""Offline, dependency-free regression tests for the simulated adapter only."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from mock_hardware_adapter import (
    ADAPTER_ID, MAX_IMAGE_BYTES, AdapterRefusal, MockReadOnlyAdapter,
    get_adapter, main, write_receipt_exclusive,
)


def fixture(tmp_path):
    path = tmp_path / 'synthetic image with spaces.bin'
    data = bytes(range(256)) + bytes(range(256))
    path.write_bytes(data)
    return path, data, hashlib.sha256(data).hexdigest()


def test_probe_never_claims_device_or_writer():
    result = get_adapter(ADAPTER_ID).probe()
    assert result['status'] == 'simulated_only'
    assert result['hardware_connected'] is False
    assert result['hardware_writes_supported'] is False
    assert result['external_dll_loaded'] is False
    assert 'upload_emulator_image' not in result['capabilities']


def test_deterministic_bound_receipt_and_no_mutation(tmp_path):
    image, original, digest = fixture(tmp_path)
    adapter = MockReadOnlyAdapter()
    a = adapter.preview_image(image, expected_sha256=digest, expected_size=len(original), declared_target_id='synthetic-target.v1')
    b = adapter.preview_image(image, expected_sha256=digest.upper(), expected_size=len(original), declared_target_id='synthetic-target.v1')
    assert a == b
    assert a['source_image']['sha256'] == digest.upper()
    assert a['hardware_connected'] is False and a['hardware_write_executed'] is False
    assert a['device_readback'] == 'not_performed'
    assert a['target_identity_verified_on_hardware'] is False
    assert len(a['evidence_sha256']) == 64
    assert image.read_bytes() == original
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize('kind', [
    'wrong_hash','invalid_hash','wrong_size','zero_size','oversize','invalid_target','missing_image'
])
def test_invalid_input_refused_without_receipt(tmp_path, kind):
    image, data, digest = fixture(tmp_path)
    kw = {'expected_sha256': digest, 'expected_size': len(data), 'declared_target_id': 'synthetic'}
    if kind == 'wrong_hash': kw['expected_sha256'] = '0' * 64
    if kind == 'invalid_hash': kw['expected_sha256'] = 'bad-hash'
    if kind == 'wrong_size': kw['expected_size'] = len(data) + 1
    if kind == 'zero_size': kw['expected_size'] = 0
    if kind == 'oversize': kw['expected_size'] = MAX_IMAGE_BYTES + 1
    if kind == 'invalid_target': kw['declared_target_id'] = '../../inject'
    if kind == 'missing_image': image = tmp_path / 'missing.bin'
    with pytest.raises(AdapterRefusal):
        MockReadOnlyAdapter().preview_image(image, **kw)
    assert not (tmp_path / 'preview.json').exists()


def test_truncated_image_refused(tmp_path):
    image, data, digest = fixture(tmp_path)
    image.write_bytes(data[:-1])
    with pytest.raises(AdapterRefusal):
        MockReadOnlyAdapter().preview_image(image, expected_sha256=digest, expected_size=len(data), declared_target_id='synthetic')


def test_refuse_unregistered_adapters():
    with pytest.raises(AdapterRefusal):
        get_adapter('vendor.flash-writer')


def test_receipt_published_exclusively_and_never_to_original(tmp_path):
    image, data, digest = fixture(tmp_path)
    r = MockReadOnlyAdapter().preview_image(image, expected_sha256=digest, expected_size=len(data), declared_target_id='synthetic')
    with pytest.raises(AdapterRefusal):
        write_receipt_exclusive(image, image, r)
    assert image.read_bytes() == data
    dest = tmp_path / 'preview receipt.json'
    write_receipt_exclusive(dest, image, r)
    assert json.loads(dest.read_text(encoding='utf-8')) == r
    with pytest.raises(AdapterRefusal):
        write_receipt_exclusive(dest, image, r)
    assert image.read_bytes() == data


def test_cli_probe_and_preview_no_device(tmp_path, capsys):
    image, data, digest = fixture(tmp_path)
    assert main(['adapter-probe']) == 0
    assert json.loads(capsys.readouterr().out)['hardware_writes_supported'] is False
    out = tmp_path / 'receipt.json'
    assert main(['adapter-preview', '--bin', str(image), '--expected-bin-sha256', digest,
                 '--expected-size', str(len(data)), '--target-id', 'synthetic', '--receipt', str(out)]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview['evidence_sha256'] == json.loads(out.read_text())['evidence_sha256']
    assert image.read_bytes() == data
    assert main(['adapter-preview', '--bin', str(image), '--expected-bin-sha256', '0' * 64,
                 '--expected-size', str(len(data)), '--target-id', 'synthetic']) == 2
    error = json.loads(capsys.readouterr().err)
    assert error['status'] == 'refused' and error['hardware_write_executed'] is False


def test_isolated_python_cli_and_optimized_mode(tmp_path):
    image, data, digest = fixture(tmp_path)
    import mock_hardware_adapter as module
    script = Path(module.__file__).resolve()
    for flag in ([], ['-O']):
        result = subprocess.run(
            [sys.executable, *flag, '-I', str(script), 'adapter-preview', '--bin', str(image),
             '--expected-bin-sha256', digest, '--expected-size', str(len(data)),
             '--target-id', 'synthetic'], cwd=tmp_path, capture_output=True,
            text=True, timeout=10,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        parsed = json.loads(result.stdout)
        assert parsed['schema'] == 'kingai.hardware-adapter-preview.v1'
        assert parsed['hardware_write_executed'] is False


def test_in_place_source_mutation_refused(tmp_path, monkeypatch):
    image, data, digest = fixture(tmp_path)
    from mock_hardware_adapter import _bounded_digest
    original = Path.stat
    calls = {'n': 0}
    def changing_stat(path, *args, **kwargs):
        ret = original(path, *args, **kwargs)
        if str(path) == str(image):
            calls['n'] += 1
            if calls['n'] == 2:
                image.write_bytes(data[:-1])
                return original(path, *args, **kwargs)
        return ret
    monkeypatch.setattr(Path, 'stat', changing_stat)
    with pytest.raises(AdapterRefusal):
        _bounded_digest(image, len(data))

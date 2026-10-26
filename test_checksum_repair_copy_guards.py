"""Actual-verifier, package-publication and preservation regression controls."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import checksum_repair_copy as adapter
from raw_patch_checksum_profiles import verify_holden_vy_060a_92118883_additive16
from test_checksum_repair_copy import synthetic, reference_sum


def make_input(tmp_path):
    data = synthetic()
    source = tmp_path / 'synthetic.bin'
    source.write_bytes(data)
    return source, data, hashlib.sha256(data).hexdigest(), tmp_path / 'output'


def test_all_verifier_calls_use_actual_api_phases_and_full_bytes(tmp_path):
    source, data, expected_hash, output = make_input(tmp_path)
    phases = []

    def verify(image, context):
        phases.append(context['phase'])
        return verify_holden_vy_060a_92118883_additive16(image, context)

    with patch.object(adapter, 'verify_holden_vy_060a_92118883_additive16', verify):
        result = adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    expected = bytearray(data)
    expected[0x4006:0x4008] = reference_sum(data).to_bytes(2, 'big')
    assert (output / result['output_filename']).read_bytes() == bytes(expected)
    assert source.read_bytes() == data
    assert phases == ['input', 'output', 'output']
    assert sorted(p.name for p in output.iterdir()) == ['receipt.json', 'synthetic.checksum-copy.bin']
    assert json.loads((output / 'receipt.json').read_text()) == result


@pytest.mark.parametrize('victim', ['source', 'output'])
def test_mutation_during_final_verifier_never_publishes_receipt(tmp_path, victim):
    source, data, expected_hash, output = make_input(tmp_path)
    calls = []

    def verify(image, context):
        calls.append(context['phase'])
        result = verify_holden_vy_060a_92118883_additive16(image, context)
        if len(calls) == 3:
            target = source if victim == 'source' else output / 'synthetic.checksum-copy.bin'
            changed = bytearray(target.read_bytes())
            changed[0x2000] ^= 1
            target.write_bytes(changed)
        return result

    with patch.object(adapter, 'verify_holden_vy_060a_92118883_additive16', verify):
        with pytest.raises(adapter.ChecksumRepairCopyError, match='before receipt publication'):
            adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    assert not (output / 'receipt.json').exists()
    assert (output / 'receipt.json.pending').exists()
    if victim == 'output':
        assert source.read_bytes() == data


def test_partial_json_failure_leaves_no_final_receipt(tmp_path):
    source, data, expected_hash, output = make_input(tmp_path)

    def broken_json(value, stream, **kwargs):
        stream.write('{')
        raise OSError('injected partial receipt failure')

    with patch.object(adapter.json, 'dump', broken_json):
        with pytest.raises(OSError, match='injected partial receipt failure'):
            adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    assert source.read_bytes() == data
    assert not (output / 'receipt.json').exists()
    assert (output / 'receipt.json.pending').read_text() == '{'


def test_receipt_collision_is_not_overwritten(tmp_path):
    source, data, expected_hash, output = make_input(tmp_path)
    original_link = adapter.os.link

    def collide(pending, final):
        Path(final).write_bytes(b'existing receipt must survive')
        return original_link(pending, final)

    with patch.object(adapter.os, 'link', collide):
        with pytest.raises(FileExistsError):
            adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    assert (output / 'receipt.json').read_bytes() == b'existing receipt must survive'
    assert source.read_bytes() == data


def test_bin_collision_is_not_overwritten(tmp_path):
    source, data, expected_hash, output = make_input(tmp_path)
    original_mkdir = Path.mkdir

    def collide(path, *args, **kwargs):
        result = original_mkdir(path, *args, **kwargs)
        if path == output:
            (output / 'synthetic.checksum-copy.bin').write_bytes(b'existing BIN')
        return result

    with patch.object(Path, 'mkdir', collide):
        with pytest.raises(FileExistsError):
            adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    assert (output / 'synthetic.checksum-copy.bin').read_bytes() == b'existing BIN'
    assert not (output / 'receipt.json').exists()
    assert source.read_bytes() == data


def test_wrong_size_refused_before_source_open(tmp_path):
    source = tmp_path / 'oversized.bin'
    source.write_bytes(b'x' * (0x20000 + 1))
    with patch.object(Path, 'open', side_effect=AssertionError('must not open wrong-sized input')):
        with pytest.raises(adapter.ChecksumRepairCopyError, match='full image'):
            adapter._read_image(source)


def test_source_reparse_attribute_refused_before_open(tmp_path):
    source, _, _, _ = make_input(tmp_path)
    real = source.lstat()
    fake = SimpleNamespace(st_mode=real.st_mode, st_file_attributes=0x400)
    with patch.object(Path, 'lstat', return_value=fake):
        with pytest.raises(adapter.ChecksumRepairCopyError, match='non-reparse'):
            adapter._read_image(source)


def test_unsupported_receipt_publication_filesystem_fails_closed(tmp_path):
    source, data, expected_hash, output = make_input(tmp_path)
    with patch.object(adapter.os, 'link', side_effect=OSError('unsupported hard link')):
        with pytest.raises(OSError, match='unsupported hard link'):
            adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    assert not (output / 'receipt.json').exists()
    assert (output / 'receipt.json.pending').exists()
    assert source.read_bytes() == data


def test_source_mutation_during_pending_receipt_write_is_detected(tmp_path):
    source, data, expected_hash, output = make_input(tmp_path)
    original_dump = json.dump

    def mutate(value, stream, **kwargs):
        original_dump(value, stream, **kwargs)
        altered = bytearray(data)
        altered[0x2000] ^= 1
        source.write_bytes(altered)

    with patch.object(adapter.json, 'dump', mutate):
        with pytest.raises(adapter.ChecksumRepairCopyError, match='before receipt publication'):
            adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    assert not (output / 'receipt.json').exists()


def test_short_bin_write_retained_without_final_receipt(tmp_path):
    source, data, expected_hash, output = make_input(tmp_path)
    original_open = Path.open

    class ShortWrite:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            self.stream.__enter__()
            return self
        def write(self, content):
            return self.stream.write(content[:len(content) // 2])
        def __exit__(self, *args):
            return self.stream.__exit__(*args)

    def open_short(path, mode='r', *args, **kwargs):
        stream = original_open(path, mode, *args, **kwargs)
        return ShortWrite(stream) if mode == 'xb' else stream

    with patch.object(Path, 'open', open_short):
        with pytest.raises(adapter.ChecksumRepairCopyError, match='incomplete checksum-copy write'):
            adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    assert (output / 'synthetic.checksum-copy.bin').stat().st_size == len(data) // 2
    assert not (output / 'receipt.json').exists()
    assert source.read_bytes() == data


def test_corrupt_staged_receipt_never_publishes(tmp_path):
    source, data, expected_hash, output = make_input(tmp_path)

    def corrupt(value, stream, **kwargs):
        stream.write('{not-json')

    with patch.object(adapter.json, 'dump', corrupt):
        with pytest.raises(adapter.ChecksumRepairCopyError, match='staged receipt changed'):
            adapter.write_repair_package(source, output, expected_sha256=expected_hash)
    assert not (output / 'receipt.json').exists()
    assert source.read_bytes() == data

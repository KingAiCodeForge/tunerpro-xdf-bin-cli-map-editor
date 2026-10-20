"""Save failures use synthetic files only and never expose partial final BINs."""
import builtins
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
import cli_map_editor as editor


@pytest.fixture
def session(tmp_path, monkeypatch):
    xdf, binary = tmp_path / 'source.xdf', tmp_path / 'source.bin'
    xdf.write_text(
        '<XDFFORMAT><XDFHEADER/>'
        '<XDFCONSTANT uniqueid="1"><title>Scalar</title><EMBEDDEDDATA mmedaddress="0"/>'
        '<MATH equation="X"/></XDFCONSTANT>'
        '<XDFFLAG><title>Flag</title><EMBEDDEDDATA mmedaddress="1"/><mask>1</mask></XDFFLAG>'
        '</XDFFORMAT>', encoding='utf-8')
    binary.write_bytes(bytes([5, 6]) + bytes(62))
    result = editor.XDFBinSession(str(xdf), str(binary))
    assert result.load()
    result.write_scalar(result.constants[0], 9)
    monkeypatch.setattr(editor, '_timestamp', lambda: 'fixed')
    return result


class FaultyWriter:
    def __init__(self, handle, fault):
        self.handle, self.fault = handle, fault

    def __enter__(self):
        self.handle.__enter__()
        return self

    def __exit__(self, *args):
        result = self.handle.__exit__(*args)
        if self.fault == 'close':
            raise OSError('synthetic close failure')
        return result

    def write(self, data):
        if self.fault == 'write':
            raise OSError('synthetic write failure')
        if self.fault == 'short':
            return self.handle.write(data[:-1])
        return self.handle.write(data)

    def flush(self):
        if self.fault == 'flush':
            raise OSError('synthetic flush failure')
        return self.handle.flush()

    def fileno(self):
        return self.handle.fileno()


def fail_payload(monkeypatch, suffix, fault):
    def open_with_fault(path, mode='r', *args, **kwargs):
        if mode == 'xb' and str(path).endswith(suffix):
            if fault == 'open':
                raise OSError('synthetic open failure')
            return FaultyWriter(builtins.open(path, mode, *args, **kwargs), fault)
        return builtins.open(path, mode, *args, **kwargs)
    monkeypatch.setattr(editor, 'open', open_with_fault, raising=False)


def assert_failed_save(session, output):
    assert Path(session.bin_path).read_bytes() == bytes([5, 6]) + bytes(62)
    assert not (output / 'source_edited_fixed.bin').exists()
    assert not (output / 'source_edited_fixed.log').exists()
    assert not (output / 'source_edited_fixed_detailed.csv').exists()
    stages = list(output.glob('.kingai-save-*.incomplete'))
    assert len(stages) == 1
    assert (stages[0] / 'save-state.json').is_file()


@pytest.mark.parametrize('suffix', ['.log', '_detailed.csv', '.bin'])
@pytest.mark.parametrize('fault', ['open', 'write', 'short', 'flush', 'close'])
def test_payload_failures_never_publish_partial_final_files(session, tmp_path, monkeypatch, suffix, fault):
    output = tmp_path / 'output'
    fail_payload(monkeypatch, suffix, fault)
    with pytest.raises(editor.SaveIncompleteError, match='INCOMPLETE save'):
        session.save_final(str(output))
    assert_failed_save(session, output)


def test_fsync_failure_keeps_all_outputs_unpublished(session, tmp_path, monkeypatch):
    output = tmp_path / 'output'
    def fail(_):
        raise OSError('synthetic fsync failure')
    monkeypatch.setattr(editor.os, 'fsync', fail)
    with pytest.raises(editor.SaveIncompleteError, match='synthetic fsync failure'):
        session.save_final(str(output))
    assert_failed_save(session, output)


@pytest.mark.parametrize('fail_at', [1, 2, 3])
def test_publish_failures_roll_back_only_this_saves_outputs(session, tmp_path, monkeypatch, fail_at):
    output = tmp_path / 'output'
    real_publish = editor._publish_staged_file
    calls = []
    def publish(staged, destination):
        calls.append(destination)
        if len(calls) == fail_at:
            raise OSError('synthetic publication failure')
        real_publish(staged, destination)
    monkeypatch.setattr(editor, '_publish_staged_file', publish)
    with pytest.raises(editor.SaveIncompleteError, match='synthetic publication failure'):
        session.save_final(str(output))
    assert_failed_save(session, output)


def test_competing_destination_created_after_preflight_is_preserved(session, tmp_path, monkeypatch):
    output = tmp_path / 'output'
    real_publish = editor._publish_staged_file
    def publish(staged, destination):
        if destination.suffix == '.bin':
            destination.write_bytes(b'concurrent file must survive')
        real_publish(staged, destination)
    monkeypatch.setattr(editor, '_publish_staged_file', publish)
    with pytest.raises(editor.SaveIncompleteError):
        session.save_final(str(output))
    assert (output / 'source_edited_fixed.bin').read_bytes() == b'concurrent file must survive'
    assert not (output / 'source_edited_fixed.log').exists()
    assert not (output / 'source_edited_fixed_detailed.csv').exists()
    assert Path(session.bin_path).read_bytes()[0] == 5


def test_successful_save_publishes_bin_last_and_removes_its_staging(session, tmp_path, monkeypatch):
    output = tmp_path / 'output'
    order = []
    real_publish = editor._publish_staged_file
    def publish(staged, destination):
        order.append(destination.suffix)
        real_publish(staged, destination)
    monkeypatch.setattr(editor, '_publish_staged_file', publish)
    bin_path, log_path = session.save_final(str(output))
    assert order == ['.log', '.csv', '.bin']
    assert Path(bin_path).read_bytes()[0] == 9
    assert Path(log_path).is_file()
    assert list(output.glob('.kingai-save-*.incomplete')) == []
    assert Path(session.bin_path).read_bytes()[0] == 5


def test_cli_save_failure_is_nonzero_without_saved_message(session, tmp_path, monkeypatch, capsys):
    output = tmp_path / 'output'
    fail_payload(monkeypatch, '.bin', 'write')
    monkeypatch.setattr(sys, 'argv', ['editor', 'edit-scalar', '--xdf', session.xdf_path,
        '--bin', session.bin_path, '--name', 'Scalar', '--value', '9',
        '--autosave', '--output-dir', str(output)])
    assert editor.main() == 1
    text = capsys.readouterr().out
    assert 'INCOMPLETE save' in text
    assert 'Saved:' not in text
    assert_failed_save(session, output)


@pytest.mark.parametrize('mask', [0, -1, 256, True, 'bad', None])
def test_preflight_rejects_invalid_flag_masks_without_mutating(session, monkeypatch, capsys, mask):
    session.flags[0]['mask'] = mask
    monkeypatch.setattr(editor, 'XDFBinSession', lambda *_: session)
    assert editor.cmd_preflight(SimpleNamespace(xdf=session.xdf_path, bin=session.bin_path)) == 1
    assert 'invalid mask' in capsys.readouterr().out
    assert Path(session.bin_path).read_bytes()[0] == 5


@pytest.mark.parametrize('mask', [1, 3, 128, 255])
def test_preflight_accepts_supported_nonzero_byte_masks(session, monkeypatch, mask):
    session.flags[0]['mask'] = mask
    monkeypatch.setattr(editor, 'XDFBinSession', lambda *_: session)
    assert editor.cmd_preflight(SimpleNamespace(xdf=session.xdf_path, bin=session.bin_path)) == 0

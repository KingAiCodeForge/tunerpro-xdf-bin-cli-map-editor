"""Portable synthetic regressions for edit selection and output preservation."""

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

import cli_map_editor as editor


def session(tmp_path, scoped=False):
    xdf = tmp_path / 'source.xdf'
    binary = tmp_path / 'source.bin'
    scope = '<MATH row="1" equation="X*2"/>' if scoped else ''
    xdf.write_text(
        '<XDFFORMAT><XDFHEADER/>'
        '<XDFCONSTANT uniqueid="1"><title>Scalar</title>'
        '<EMBEDDEDDATA mmedaddress="0"/><MATH equation="X"/></XDFCONSTANT>'
        '<XDFFLAG><title>Flag</title><EMBEDDEDDATA mmedaddress="0"/><mask>1</mask></XDFFLAG>'
        '<XDFTABLE uniqueid="2"><title>Table</title><XDFAXIS id="z">'
        '<EMBEDDEDDATA mmedaddress="0" mmedrowcount="2" mmedcolcount="1"/>'
        f'<MATH equation="X"/>{scope}</XDFAXIS></XDFTABLE></XDFFORMAT>', encoding='utf-8')
    binary.write_bytes(bytes([5, 6]) + bytes(62))
    result = editor.XDFBinSession(str(xdf), str(binary))
    assert result.load()
    return result


@pytest.mark.parametrize('raw_mode', [False, True])
def test_scoped_table_write_is_refused_without_mutation(tmp_path, raw_mode):
    result = session(tmp_path, scoped=True)
    before = bytes(result.bin_data)
    assert result.read_table_data(result.tables[0]) == [[5], [12]]
    with pytest.raises(ValueError, match='Scoped table equations are read-only'):
        result.write_table_cell(result.tables[0], 2, 1, 20, raw_mode=raw_mode)
    assert bytes(result.bin_data) == before
    assert result.changes == []


@pytest.mark.parametrize('command', [editor.cmd_batch, editor.cmd_port, editor.cmd_save])
def test_disabled_commands_refuse_before_loading_or_writing(tmp_path, monkeypatch, command):
    monkeypatch.setattr(editor, 'XDFBinSession', lambda *_: pytest.fail('Session must not load'))
    assert command(SimpleNamespace(output_dir=str(tmp_path / 'output'))) == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('command', [editor.cmd_edit, editor.cmd_edit_scalar, editor.cmd_edit_flag])
@pytest.mark.parametrize(('autosave', 'output_dir'), [(False, 'output'), (True, None)])
def test_edits_require_autosave_and_destination_before_loading(monkeypatch, command, autosave, output_dir):
    monkeypatch.setattr(editor, 'XDFBinSession', lambda *_: pytest.fail('Session must not load'))
    assert command(SimpleNamespace(autosave=autosave, output_dir=output_dir)) == 1


def test_temp_save_cannot_write_unbound_bin(tmp_path):
    result = session(tmp_path)
    with pytest.raises(ValueError, match='Temporary saves are disabled'):
        result.save_temp()
    assert not Path(result.bin_path + '.edited.tmp').exists()


@pytest.mark.parametrize('kind', ['tables', 'constants', 'flags'])
@pytest.mark.parametrize(('titles', 'lookup'), [
    (['Duplicate', 'Duplicate'], 'Duplicate'), (['Duplicate', 'DUPLICATE'], 'duplicate'),
])
def test_ambiguous_names_cannot_select_first_object(tmp_path, kind, titles, lookup):
    result = session(tmp_path)
    result.exporter.elements[kind] = [{'title': title, 'address': i} for i, title in enumerate(titles)]
    method = {'tables': result.find_table, 'constants': result.find_constant, 'flags': result.find_flag}[kind]
    before = bytes(result.bin_data)
    with pytest.raises(ValueError, match='Ambiguous'):
        method(lookup)
    assert bytes(result.bin_data) == before


def test_invalid_scalar_log_format_does_not_mutate_bytes(tmp_path):
    result = session(tmp_path)
    scalar = result.constants[0]
    scalar['decimalpl'] = -1
    before = bytes(result.bin_data)
    with pytest.raises(ValueError):
        result.write_scalar(scalar, 9)
    assert bytes(result.bin_data) == before
    assert result.changes == [] and result.log_entries == []


@pytest.mark.parametrize('existing_suffix', ['.bin', '.log', '_detailed.csv'])
def test_save_preflights_every_output_before_creating_any(tmp_path, monkeypatch, existing_suffix):
    result = session(tmp_path)
    monkeypatch.setattr(editor, '_timestamp', lambda: 'fixed')
    output = tmp_path / 'output'
    output.mkdir()
    existing = output / f'source_edited_fixed{existing_suffix}'
    existing.write_bytes(b'preserve')
    result.write_scalar(result.constants[0], 9)
    with pytest.raises(FileExistsError, match='Refusing to overwrite'):
        result.save_final(str(output))
    assert existing.read_bytes() == b'preserve'
    assert list(output.iterdir()) == [existing]
    assert Path(result.bin_path).read_bytes()[0] == 5


def test_save_refuses_input_alias_before_creating_logs(tmp_path, monkeypatch):
    result = session(tmp_path)
    before = Path(result.bin_path).read_bytes()
    monkeypatch.setattr(editor, '_output_name', lambda *_: 'source.bin')
    with pytest.raises(ValueError, match='input files'):
        result.save_final(str(tmp_path))
    assert Path(result.bin_path).read_bytes() == before
    assert sorted(path.name for path in tmp_path.iterdir()) == ['source.bin', 'source.xdf']


def test_successful_autosave_creates_audited_copy_and_no_temp(tmp_path, monkeypatch):
    result = session(tmp_path)
    output = tmp_path / 'output'
    monkeypatch.setattr(editor, '_timestamp', lambda: 'fixed')
    monkeypatch.setattr(sys, 'argv', ['editor', 'edit-scalar', '--xdf', result.xdf_path,
        '--bin', result.bin_path, '--name', 'Scalar', '--value', '9',
        '--autosave', '--output-dir', str(output)])
    assert editor.main() == 0
    assert (output / 'source_edited_fixed.bin').read_bytes()[0] == 9
    assert Path(result.bin_path).read_bytes()[0] == 5
    assert (output / 'source_edited_fixed.log').is_file()
    assert (output / 'source_edited_fixed_detailed.csv').is_file()
    assert not Path(result.bin_path + '.edited.tmp').exists()
    # Repeating inside the same timestamp window must preserve all outputs.
    saved = {path.name: path.read_bytes() for path in output.iterdir()}
    assert editor.main() == 1
    assert {path.name: path.read_bytes() for path in output.iterdir()} == saved


def test_scoped_cli_edit_returns_failure_without_output_or_temp(tmp_path, monkeypatch, capsys):
    result = session(tmp_path, scoped=True)
    output = tmp_path / 'output'
    monkeypatch.setattr(sys, 'argv', ['editor', 'edit', '--xdf', result.xdf_path,
        '--bin', result.bin_path, '--map', 'Table', '--rows', '2', '--cols', '1',
        '--value', '20', '--autosave', '--output-dir', str(output)])
    assert editor.main() == 1
    assert not output.exists()
    assert not Path(result.bin_path + '.edited.tmp').exists()
    captured = capsys.readouterr()
    assert 'Scoped table equations are read-only' in captured.out
    assert 'Traceback' not in captured.err


def test_unequal_length_diff_fails_instead_of_claiming_zero_changes(tmp_path, capsys):
    first, second = tmp_path / 'short.bin', tmp_path / 'long.bin'
    first.write_bytes(b'\x01')
    second.write_bytes(b'\x01\x02')
    assert editor.cmd_diff(SimpleNamespace(bin_a=str(first), bin_b=str(second))) == 1
    output = capsys.readouterr().out
    assert 'equal-length BINs are required' in output
    assert 'Changed bytes: 0' not in output


def test_snapshot_uses_new_directory_and_preserves_existing_snapshot(tmp_path, monkeypatch):
    result = session(tmp_path)
    output = tmp_path / 'snapshots'
    args = SimpleNamespace(xdf=result.xdf_path, bin=result.bin_path, output_dir=str(output))
    monkeypatch.setattr(editor, '_timestamp', lambda: 'fixed')
    assert editor.cmd_export(args) == 0
    snapshot = output / 'source_snapshot_fixed'
    saved = {path.name: path.read_bytes() for path in snapshot.iterdir()}
    assert saved['source_snapshot_fixed.bin'] == Path(result.bin_path).read_bytes()
    assert editor.cmd_export(args) == 1
    assert {path.name: path.read_bytes() for path in snapshot.iterdir()} == saved


def test_invalid_snapshot_definition_creates_no_output(tmp_path, monkeypatch):
    result = session(tmp_path)
    xdf = Path(result.xdf_path)
    xdf.write_text(xdf.read_text(encoding='utf-8').replace('equation="X"', 'equation="UNSUPPORTED(X)"'),
                   encoding='utf-8')
    output = tmp_path / 'snapshots'
    assert editor.cmd_export(SimpleNamespace(xdf=result.xdf_path, bin=result.bin_path,
                                             output_dir=str(output))) == 1
    assert not output.exists()
    assert Path(result.bin_path).read_bytes()[0] == 5

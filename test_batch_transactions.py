"""Synthetic end-to-end regression tests for transactional XDF/BIN CSV editing."""

import csv
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

import cli_map_editor as editor
from test_editor_exporter_contract import make_session, SCALAR_OFFSET, TABLE_OFFSET


def write_csv(path, records):
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['type', 'map', 'row', 'col', 'value', 'raw'])
        writer.writerows(records)
    return str(path)


def invoke(monkeypatch, session, plan, *extra):
    monkeypatch.setattr(sys, 'argv', [
        'editor', 'batch', '--xdf', session.xdf_path, '--bin', session.bin_path,
        '--csv', plan, *extra,
    ])
    return editor.main()


def test_batch_writes_three_targets_one_new_bin_and_audit(tmp_path, monkeypatch):
    session, original = make_session(tmp_path)
    plan = write_csv(tmp_path / 'plan.csv', [
        ('scalar', 'Scaled scalar', '', '', '-8.2', ''),
        ('table', 'Scaled table', '1', '1', '7.3', ''),
        ('table', 'Scaled table', '2', '3', '8.5', ''),
    ])
    monkeypatch.setattr(editor, '_timestamp', lambda: 'fixed')
    out = tmp_path / 'out'
    assert invoke(monkeypatch, session, plan, '--autosave', '--output-dir', str(out)) == 0
    expected = bytearray(original)
    struct.pack_into('<h', expected, SCALAR_OFFSET, -13)
    struct.pack_into('<h', expected, TABLE_OFFSET, 13)
    struct.pack_into('<h', expected, TABLE_OFFSET + 10, 15)
    assert (out / 'synthetic_batch_fixed.bin').read_bytes() == bytes(expected)
    assert Path(session.bin_path).read_bytes() == original
    assert (out / 'synthetic_batch_fixed.log').is_file()
    with (out / 'synthetic_batch_fixed_detailed.csv').open(newline='') as stream:
        details = list(csv.DictReader(stream))
    assert len(details) == 3
    assert [row['TYPE'] for row in details] == ['scalar', 'table', 'table']


def test_batch_preview_is_read_only_and_expands_ranges(tmp_path, monkeypatch, capsys):
    session, original = make_session(tmp_path)
    plan = write_csv(tmp_path / 'plan.csv', [
        ('table', 'Scaled table', '1', '1-3', '7.3', ''),
    ])
    assert invoke(monkeypatch, session, plan) == 0
    assert 'DRY RUN' in capsys.readouterr().out
    assert Path(session.bin_path).read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        'plan.csv', 'synthetic.bin', 'synthetic.xdf'
    ]


def test_batch_rejects_duplicate_byte_write_without_output(tmp_path, monkeypatch, capsys):
    session, original = make_session(tmp_path)
    plan = write_csv(tmp_path / 'plan.csv', [
        ('table', 'Scaled table', '1', '1', '7.3', ''),
        ('table', 'Scaled table', '1', '1', '7.3', ''),
    ])
    out = tmp_path / 'out'
    assert invoke(monkeypatch, session, plan, '--autosave', '--output-dir', str(out)) == 1
    assert 'Conflicting XDF writes' in capsys.readouterr().out
    assert Path(session.bin_path).read_bytes() == original
    assert not out.exists()


def test_batch_late_invalid_target_rolls_back_without_output(tmp_path, monkeypatch, capsys):
    session, original = make_session(tmp_path)
    plan = write_csv(tmp_path / 'plan.csv', [
        ('table', 'Scaled table', '1', '1', '7.3', ''),
        ('scalar', 'Missing', '', '', '6', ''),
    ])
    out = tmp_path / 'out'
    assert invoke(monkeypatch, session, plan, '--autosave', '--output-dir', str(out)) == 1
    assert 'not found' in capsys.readouterr().out
    assert Path(session.bin_path).read_bytes() == original
    assert not out.exists()


def test_batch_wrong_hash_and_invalid_raw_refuse_before_save(tmp_path, monkeypatch, capsys):
    session, original = make_session(tmp_path)
    plan = write_csv(tmp_path / 'plan.csv', [('scalar', 'Scaled scalar', '', '', '4', '')])
    out = tmp_path / 'out'
    assert invoke(monkeypatch, session, plan, '--expected-bin-sha256', '0'*64,
                  '--autosave', '--output-dir', str(out)) == 1
    assert 'BIN SHA-256 does not match' in capsys.readouterr().out
    plan = write_csv(tmp_path / 'plan.csv', [('scalar', 'Scaled scalar', '', '', '2.5', 'true')])
    assert invoke(monkeypatch, session, plan, '--autosave', '--output-dir', str(out)) == 1
    assert 'raw value must be an integer' in capsys.readouterr().out
    assert Path(session.bin_path).read_bytes() == original
    assert not out.exists()


def test_batch_sets_disjoint_flag_bits_in_same_byte(tmp_path, monkeypatch):
    session, original = make_session(tmp_path)
    definition = ET.parse(session.xdf_path)
    root = definition.getroot()
    for i, name in enumerate(('Flag A', 'Flag B')):
        flag = ET.SubElement(root, 'XDFFLAG', uniqueid=str(20 + i))
        ET.SubElement(flag, 'title').text = name
        ET.SubElement(flag, 'EMBEDDEDDATA', mmedaddress='0xA0')
        ET.SubElement(flag, 'mask').text = str(1 << i)
    definition.write(session.xdf_path, encoding='utf-8', xml_declaration=True)
    plan = write_csv(tmp_path / 'plan.csv', [
        ('flag', 'Flag A', '', '', 'set', ''),
        ('flag', 'Flag B', '', '', 'on', ''),
    ])
    out = tmp_path / 'out'
    monkeypatch.setattr(editor, '_timestamp', lambda: 'fixed')
    assert invoke(monkeypatch, session, plan, '--autosave', '--output-dir', str(out)) == 0
    expected = bytearray(original)
    expected[0xC0] |= 0x03
    assert (out / 'synthetic_batch_fixed.bin').read_bytes() == bytes(expected)

"""End-to-end CLI candidate tests with synthetic XDF/BIN (requires pinned Exporter).

These are intentionally separate from dependency-free coordinator tests. Never
claim them executed solely because their source is committed.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

import cli_map_editor as editor
from test_editor_exporter_contract import make_session, SCALAR_OFFSET, TABLE_OFFSET


def _plan(tmp_path, session, operations, **overrides):
    body = {
        'schema': 'kingai.xdf-batch-plan.v1',
        'source_bin_sha256': hashlib.sha256(Path(session.bin_path).read_bytes()).hexdigest(),
        'xdf_sha256': hashlib.sha256(Path(session.xdf_path).read_bytes()).hexdigest(),
        'operations': operations,
    }
    body.update(overrides)
    plan = tmp_path / 'plan.json'
    plan.write_text(json.dumps(body, indent=2) + '\n', encoding='utf-8')
    return plan


def _cli(monkeypatch, session, plan, *args):
    monkeypatch.setattr(sys, 'argv', [
        'kingai-map-editor', 'batch', '--xdf', session.xdf_path,
        '--bin', session.bin_path, '--plan-json', str(plan), *args,
    ])
    return editor.main()


def test_hash_pinned_json_mixed_edit_creates_single_audited_bin(tmp_path, monkeypatch, capsys):
    session, before = make_session(tmp_path)
    plan = _plan(tmp_path, session, [
        {'type':'scalar','map':'Scaled scalar','uniqueid':'0x1',
         'value':-8.2,'expected_raw':-20},
        {'type':'table','map':'Scaled table','uniqueid':'0x2',
         'row':1,'col':1,'value':7.3,'expected_raw':-4},
    ])
    monkeypatch.setattr(editor, '_timestamp', lambda: 'fixed')
    out = tmp_path / 'results'
    assert _cli(monkeypatch, session, plan, '--autosave', '--output-dir', str(out), '--json') == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['schema'] == 'kingai.xdf-batch.v1'
    assert receipt['status'] == 'saved'
    assert receipt['plan']['format'] == 'json'
    assert receipt['typed_targets'] == 2
    expected = bytearray(before)
    struct.pack_into('<h', expected, SCALAR_OFFSET, -13)
    struct.pack_into('<h', expected, TABLE_OFFSET, 13)
    saved = out / 'synthetic_batch_fixed.bin'
    assert saved.read_bytes() == bytes(expected)
    assert Path(session.bin_path).read_bytes() == before
    assert (out / 'synthetic_batch_fixed.log').is_file()
    assert (out / 'synthetic_batch_fixed_detailed.csv').is_file()
    assert receipt['saved_bin'] == str(saved)


def test_json_error_is_parseable_and_leaves_no_bin(tmp_path, monkeypatch, capsys):
    session, before = make_session(tmp_path)
    plan = _plan(tmp_path, session, [
        {'type':'scalar','map':'Scaled scalar','value':-8.2},
    ], source_bin_sha256='0'*64)
    out = tmp_path / 'results'
    assert _cli(monkeypatch, session, plan, '--autosave', '--output-dir', str(out), '--json') == 1
    error = json.loads(capsys.readouterr().out)
    assert error['schema'] == 'kingai.xdf-batch-error.v1'
    assert error['status'] == 'error'
    assert 'SHA-256 does not match' in error['error']
    assert error['saved_bin'] is None
    assert not out.exists()
    assert Path(session.bin_path).read_bytes() == before


def test_duplicate_title_uses_exact_uniqueid_instead_of_first_match(tmp_path, monkeypatch):
    session, before = make_session(tmp_path)
    tree = ET.parse(session.xdf_path)
    duplicate = ET.SubElement(tree.getroot(), 'XDFCONSTANT', uniqueid='0x3')
    ET.SubElement(duplicate, 'title').text = 'Scaled scalar'
    ET.SubElement(duplicate, 'EMBEDDEDDATA', mmedaddress='0x30',
                  mmedelementsizebits='16', mmedtypeflags='0x03')
    ET.SubElement(duplicate, 'MATH', equation='X')
    tree.write(session.xdf_path, encoding='utf-8', xml_declaration=True)
    plan = _plan(tmp_path, session, [
        {'type':'scalar','map':'Scaled scalar','uniqueid':'0x3',
         'address':'0x30', 'raw': True,'value':7},
    ])
    monkeypatch.setattr(editor, '_timestamp', lambda: 'fixed')
    out = tmp_path / 'results'
    assert _cli(monkeypatch, session, plan, '--autosave', '--output-dir', str(out)) == 0
    expected = bytearray(before)
    struct.pack_into('<h', expected, 0x50, 7)
    assert (out / 'synthetic_batch_fixed.bin').read_bytes() == bytes(expected)
    assert expected[SCALAR_OFFSET:SCALAR_OFFSET+2] == before[SCALAR_OFFSET:SCALAR_OFFSET+2]

"""Pinned-Exporter integration contracts for untyped XDF raw VAR aliases.

Requires the exact installed Universal Exporter. Synthetic XDF/BIN only.
Committed here, but not executed in environments lacking that dependency.
"""
from pathlib import Path
import hashlib
import json
import struct
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
import cli_map_editor as editor


def synthetic_session(tmp_path):
    root = ET.Element('XDFFORMAT', version='1.60')
    header = ET.SubElement(root, 'XDFHEADER')
    ET.SubElement(header, 'BASEOFFSET', offset='0', subtract='0')
    const = ET.SubElement(root, 'XDFCONSTANT', uniqueid='0x1')
    ET.SubElement(const, 'title').text = 'Raw alias scalar'
    ET.SubElement(const, 'EMBEDDEDDATA', mmedaddress='0x10',
                  mmedelementsizebits='16', mmedtypeflags='0x03')
    ET.SubElement(const, 'decimalpl').text = '3'
    math = ET.SubElement(const, 'MATH', equation='w/160')
    ET.SubElement(math, 'VAR', id='w')
    table = ET.SubElement(root, 'XDFTABLE', uniqueid='0x2')
    ET.SubElement(table, 'title').text = 'Raw alias table'
    for name, count in (('x',2), ('y',1)):
        axis = ET.SubElement(table, 'XDFAXIS', id=name)
        ET.SubElement(axis, 'indexcount').text = str(count)
        for i in range(count):
            ET.SubElement(axis, 'LABEL', index=str(i), value=str(i))
    z = ET.SubElement(table, 'XDFAXIS', id='z')
    ET.SubElement(z, 'EMBEDDEDDATA', mmedaddress='0x40',
                  mmedelementsizebits='16', mmedtypeflags='0x03',
                  mmedrowcount='1', mmedcolcount='2')
    math = ET.SubElement(z, 'MATH', equation='w/160')
    ET.SubElement(math, 'VAR', id='w')

    xdf=tmp_path/'alias.xdf'
    binary=tmp_path/'alias.bin'
    ET.ElementTree(root).write(xdf, encoding='utf-8', xml_declaration=True)
    source=bytearray(128)
    struct.pack_into('<h', source, 0x10, 160)
    struct.pack_into('<h', source, 0x40, 320)
    struct.pack_into('<h', source, 0x42, 480)
    binary.write_bytes(source)
    session=editor.XDFBinSession(str(xdf),str(binary))
    assert session.load()
    return session,bytes(source)


def test_scalar_raw_alias_uses_declared_math_for_old_and_new(tmp_path):
    s,source=synthetic_session(tmp_path)
    scalar=s.find_constant('Raw alias scalar')
    assert s.read_scalar_value(scalar)[1] == 1
    change=s.write_scalar(scalar,800,raw_mode=True)
    assert change['new_raw']==800
    assert change['old_real']==1
    assert change['new_real']==5
    assert s.bin_data[0x10:0x12]==struct.pack('<h',800)
    assert Path(s.bin_path).read_bytes()==source


def test_table_raw_alias_in_individual_and_range_ops(tmp_path):
    s,source=synthetic_session(tmp_path)
    table=s.find_table('Raw alias table')
    change=s.write_table_cell(table,1,1,640,raw_mode=True)
    assert change['old_real']==2 and change['new_real']==4
    changes=s.write_table_range(table,range(1,2),range(2,3),800,raw_mode=True)
    assert len(changes)==1
    assert changes[0]['old_real']==3 and changes[0]['new_real']==5
    assert s.read_table_data(table)==[[4,5]]
    assert Path(s.bin_path).read_bytes()==source


def test_batch_json_raw_alias_saves_one_new_image(tmp_path):
    s,source=synthetic_session(tmp_path)
    plan=tmp_path/'plan.json'
    plan.write_text(json.dumps({
        'schema':'kingai.xdf-batch-plan.v1',
        'source_bin_sha256':hashlib.sha256(Path(s.bin_path).read_bytes()).hexdigest(),
        'xdf_sha256':hashlib.sha256(Path(s.xdf_path).read_bytes()).hexdigest(),
        'operations': [
            {'type':'scalar','map':'Raw alias scalar','value':800,'raw':True,'expected_raw':160},
            {'type':'table','map':'Raw alias table','row':1,'col':'1-2','value':640,'raw':True},
        ],
    }),encoding='utf-8')
    target=tmp_path/'out'
    args=SimpleNamespace(xdf=s.xdf_path,bin=s.bin_path,plan_json=str(plan),csv=None,
                         autosave=True,output_dir=str(target),json=False,
                         default_map=None,expected_bin_sha256=None,expected_xdf_sha256=None)
    assert editor.cmd_batch(args)==0
    output=list(target.glob('*_batch_*.bin'))
    assert len(output)==1
    edited=output[0].read_bytes()
    assert struct.unpack_from('<h', edited,0x10)[0]==800
    assert struct.unpack_from('<h', edited,0x40)[0]==640
    assert struct.unpack_from('<h', edited,0x42)[0]==640
    assert Path(s.bin_path).read_bytes()==source


def test_bool_flag_mask_is_not_accepted_even_for_a_single_edit(tmp_path):
    s,source=synthetic_session(tmp_path)
    flag={'title':'Boolean-masked bad flag','address':0x10,'mask':True}
    with pytest.raises(ValueError,match='invalid mask'):
        s.write_flag(flag,True)
    assert Path(s.bin_path).read_bytes()==source
    assert s.bin_data==bytearray(source)
    assert not s.changes

"""Synthetic XDF/BIN contracts between the editor and its installed exporter.

The fixtures contain no vehicle data. Expected byte offsets and values are
calculated independently of the exporter's addressing and conversion helpers.
"""

from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import pytest

from cli_map_editor import XDFBinSession


SCALAR_OFFSET = 0x40
TABLE_OFFSET = 0x60


def make_session(tmp_path, *, subtract=0, scalar_equation="X*0.25-5",
                 table_equation="X*0.5+1", floating=False):
    """Write a complete small definition with signed, little-endian storage."""
    base_offset = 0x20

    def address(file_offset):
        return file_offset + base_offset if subtract else file_offset - base_offset

    root = ET.Element("XDFFORMAT", version="1.60")
    header = ET.SubElement(root, "XDFHEADER")
    ET.SubElement(header, "deftitle").text = "Synthetic editor contract"
    ET.SubElement(header, "BASEOFFSET", offset=str(base_offset), subtract=str(subtract))
    ET.SubElement(header, "REGION", type="0xFFFFFFFF", startaddress="0",
                  size="0x100", regionflags="0", name="Synthetic image")
    size_bits = 32 if floating else 16
    flags = "0x10002" if floating else "0x03"

    scalar = ET.SubElement(root, "XDFCONSTANT", uniqueid="0x1", flags="0x0")
    ET.SubElement(scalar, "title").text = "Scaled scalar"
    ET.SubElement(scalar, "EMBEDDEDDATA", mmedaddress=hex(address(SCALAR_OFFSET)),
                  mmedelementsizebits=str(size_bits), mmedtypeflags=flags)
    ET.SubElement(scalar, "decimalpl").text = "2"
    ET.SubElement(scalar, "units").text = "units"
    scalar_math = ET.SubElement(scalar, "MATH", equation=scalar_equation)
    ET.SubElement(scalar_math, "VAR", id="X")

    table = ET.SubElement(root, "XDFTABLE", uniqueid="0x2", flags="0x0")
    ET.SubElement(table, "title").text = "Scaled table"
    for axis_id, count in (("x", 3), ("y", 2)):
        axis = ET.SubElement(table, "XDFAXIS", id=axis_id)
        ET.SubElement(axis, "indexcount").text = str(count)
        for index in range(count):
            ET.SubElement(axis, "LABEL", index=str(index), value=str(index))
    z_axis = ET.SubElement(table, "XDFAXIS", id="z")
    ET.SubElement(z_axis, "EMBEDDEDDATA", mmedaddress=hex(address(TABLE_OFFSET)),
                  mmedelementsizebits=str(size_bits), mmedtypeflags=flags,
                  mmedrowcount="2", mmedcolcount="3", mmedmajorstridebits="0",
                  mmedminorstridebits="0")
    ET.SubElement(z_axis, "decimalpl").text = "2"
    table_math = ET.SubElement(z_axis, "MATH", equation=table_equation)
    ET.SubElement(table_math, "VAR", id="X")

    xdf_path = tmp_path / "synthetic.xdf"
    bin_path = tmp_path / "synthetic.bin"
    ET.ElementTree(root).write(xdf_path, encoding="utf-8", xml_declaration=True)
    original = bytearray((index * 17 + 3) % 256 for index in range(256))
    storage = "<f" if floating else "<h"
    width = size_bits // 8
    struct.pack_into(storage, original, SCALAR_OFFSET, -20)
    for index, value in enumerate((-4, -2, 0, 2, 4, 6)):
        struct.pack_into(storage, original, TABLE_OFFSET + index * width, value)
    bin_path.write_bytes(original)
    session = XDFBinSession(str(xdf_path), str(bin_path))
    assert session.load()
    assert len(session.constants) == 1
    assert len(session.tables) == 1
    return session, bytes(original)


@pytest.mark.parametrize("subtract", [0, 1], ids=["base-add", "base-subtract"])
def test_scalar_signed_little_endian_affine_quantization(tmp_path, subtract):
    session, original = make_session(tmp_path, subtract=subtract)
    scalar = session.find_constant("Scaled scalar")
    assert session.read_scalar_value(scalar) == (-20, -10.0)

    change = session.write_scalar(scalar, -8.2)

    # (-8.2 + 5) / 0.25 rounds to -13, stored as little-endian signed int16.
    expected = bytearray(original)
    expected[SCALAR_OFFSET:SCALAR_OFFSET + 2] = b"\xf3\xff"
    assert session.bin_data == expected
    assert session.read_scalar_value(scalar) == (-13, -8.25)
    assert change["old_raw"] == -20
    assert change["new_raw"] == -13
    assert change["new_real"] == -8.25
    assert int(change["file_offset"], 16) == SCALAR_OFFSET
    assert Path(session.bin_path).read_bytes() == original


@pytest.mark.parametrize("subtract", [0, 1], ids=["base-add", "base-subtract"])
@pytest.mark.parametrize(("row", "col"), [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)])
def test_contiguous_table_cell_write_and_scaled_readback(tmp_path, subtract, row, col):
    session, original = make_session(tmp_path, subtract=subtract)
    table = session.find_table("Scaled table")
    assert session.get_table_dimensions(table) == (2, 3)
    assert session.read_table_data(table) == [[-1.0, 0.0, 1.0], [2.0, 3.0, 4.0]]

    change = session.write_table_cell(table, row, col, 7.3)

    # (7.3 - 1) / 0.5 rounds to 13, whose actual engineering value is 7.5.
    offset = TABLE_OFFSET + ((row - 1) * 3 + col - 1) * 2
    expected = bytearray(original)
    expected[offset:offset + 2] = b"\x0d\x00"
    assert session.bin_data == expected
    expected_values = [[-1.0, 0.0, 1.0], [2.0, 3.0, 4.0]]
    expected_values[row - 1][col - 1] = 7.5
    assert session.read_table_data(table) == expected_values
    assert change["new_raw"] == 13
    assert change["new_real"] == 7.5
    assert int(change["file_offset"], 16) == offset
    assert Path(session.bin_path).read_bytes() == original


def write_item(session, kind, value, raw_mode=False):
    if kind == "scalar":
        return session.write_scalar(session.constants[0], value, raw_mode=raw_mode)
    return session.write_table_cell(session.tables[0], 1, 1, value, raw_mode=raw_mode)


def assert_unmodified(session, original):
    assert bytes(session.bin_data) == original
    assert Path(session.bin_path).read_bytes() == original
    assert session.changes == []
    assert session.log_entries == []


@pytest.mark.parametrize("kind", ["scalar", "table"])
@pytest.mark.parametrize(("value", "raw_mode"), [
    (100_000, False), (-100_000, False), (32768, True), (-32769, True),
])
def test_out_of_range_write_preserves_memory_source_and_audit(tmp_path, kind, value, raw_mode):
    session, original = make_session(tmp_path)
    with pytest.raises(ValueError, match="out of range"):
        write_item(session, kind, value, raw_mode)
    assert_unmodified(session, original)


@pytest.mark.parametrize("kind", ["scalar", "table"])
@pytest.mark.parametrize("raw_mode", [False, True])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_write_preserves_memory_source_and_audit(tmp_path, kind, raw_mode, value):
    session, original = make_session(tmp_path)
    with pytest.raises(ValueError, match="finite"):
        write_item(session, kind, value, raw_mode)
    assert_unmodified(session, original)


@pytest.mark.parametrize("kind", ["scalar", "table"])
@pytest.mark.parametrize("equation", ["X*X", "X*0+7"])
def test_noninvertible_engineering_write_is_rejected_without_mutation(tmp_path, kind, equation):
    session, original = make_session(tmp_path, scalar_equation=equation, table_equation=equation)
    with pytest.raises(ValueError, match="Cannot convert"):
        write_item(session, kind, 9)
    assert_unmodified(session, original)


@pytest.mark.parametrize("kind", ["scalar", "table"])
@pytest.mark.parametrize("raw_mode", [False, True])
def test_float_storage_remains_readable_but_write_is_rejected(tmp_path, kind, raw_mode):
    session, original = make_session(tmp_path, floating=True)
    assert session.read_scalar_value(session.constants[0]) == (-20.0, -10.0)
    assert session.read_table_data(session.tables[0]) == [[-1.0, 0.0, 1.0], [2.0, 3.0, 4.0]]
    with pytest.raises(ValueError, match="storage type"):
        write_item(session, kind, 9, raw_mode)
    assert_unmodified(session, original)


@pytest.mark.parametrize("definition", [
    '<XDFFORMAT><XDFHEADER></XDFFORMAT>',
    '<XDFFORMAT><XDFCONSTANT title="unterminated></XDFCONSTANT></XDFFORMAT>',
])
def test_malformed_definition_does_not_create_mutable_session(tmp_path, definition):
    xdf_path = tmp_path / "invalid.xdf"
    bin_path = tmp_path / "synthetic.bin"
    xdf_path.write_text(definition, encoding="utf-8")
    original = bytes(range(256))
    bin_path.write_bytes(original)
    session = XDFBinSession(str(xdf_path), str(bin_path))

    assert session.load() is False
    assert session.bin_data is None
    assert session.changes == []
    assert session.log_entries == []
    assert bin_path.read_bytes() == original

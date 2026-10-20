"""Public-source review regressions using generated XML and bytes only."""

import csv
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

import cli_map_editor as editor


SCALAR = 0x20
TABLE = 0x40


def make_case(tmp_path, equation="X", linked=False):
    root = ET.Element("XDFFORMAT", version="1.60")
    header = ET.SubElement(root, "XDFHEADER")
    ET.SubElement(header, "REGION", size="0x100", startaddress="0")
    scalar = ET.SubElement(root, "XDFCONSTANT", uniqueid="1")
    ET.SubElement(scalar, "title").text = "Scalar"
    ET.SubElement(scalar, "EMBEDDEDDATA", mmedaddress=hex(SCALAR),
                  mmedelementsizebits="8", mmedtypeflags="0")
    math = ET.SubElement(scalar, "MATH", equation="X" if linked else equation)
    ET.SubElement(math, "VAR", id="X")
    table = ET.SubElement(root, "XDFTABLE", uniqueid="2")
    ET.SubElement(table, "title").text = "Table"
    axis = ET.SubElement(table, "XDFAXIS", id="z")
    ET.SubElement(axis, "EMBEDDEDDATA", mmedaddress=hex(TABLE),
                  mmedelementsizebits="8", mmedtypeflags="0",
                  mmedrowcount="2", mmedcolcount="1")
    math = ET.SubElement(axis, "MATH", equation=equation)
    ET.SubElement(math, "VAR", id="X")
    if linked:
        ET.SubElement(math, "VAR", id="Y", type="address", address=hex(TABLE + 1))
    xdf, binary = tmp_path / "synthetic.xdf", tmp_path / "synthetic.bin"
    ET.ElementTree(root).write(xdf, encoding="utf-8", xml_declaration=True)
    original = bytearray((index * 17 + 3) % 256 for index in range(256))
    original[SCALAR] = 8
    original[TABLE:TABLE + 3] = bytes([2, 3, 0xA5])
    binary.write_bytes(original)
    session = editor.XDFBinSession(str(xdf), str(binary))
    assert session.load()
    return session, bytes(original)


def write_item(session, kind, value, raw=False):
    if kind == "scalar":
        return session.write_scalar(session.constants[0], value, raw_mode=raw)
    return session.write_table_cell(session.tables[0], 1, 1, value, raw_mode=raw)


def assert_unchanged(session, original):
    assert bytes(session.bin_data) == original
    assert Path(session.bin_path).read_bytes() == original
    assert session.changes == []
    assert session.log_entries == []


def test_cli_range_refuses_later_write_that_invalidates_earlier_cell(tmp_path, monkeypatch, capsys):
    session, original = make_case(tmp_path, "X+if(A==0;Y;0)", linked=True)
    output = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", ["editor", "edit", "--xdf", session.xdf_path,
        "--bin", session.bin_path, "--map", "Table", "--rows", "1-2", "--cols", "1",
        "--value", "10", "--autosave", "--output-dir", str(output)])
    assert editor.main() == 1
    assert "conversion dependency" in capsys.readouterr().out
    assert not output.exists()
    assert Path(session.bin_path).read_bytes() == original


@pytest.mark.parametrize("prior_edit", [False, True])
def test_range_dependency_failure_restores_prior_session_state(tmp_path, prior_edit):
    session, original = make_case(tmp_path, "X+if(A==0;Y;0)", linked=True)
    # The scalar is deliberately not used; retain an existing table edit instead.
    if prior_edit:
        session.write_table_cell(session.tables[0], 1, 1, 6.0)
    before, changes = bytes(session.bin_data), list(session.changes)
    with pytest.raises(ValueError, match="conversion dependency"):
        session.write_table_range(session.tables[0], range(1, 3), range(1, 2), 10.0)
    assert bytes(session.bin_data) == before
    assert session.changes == changes
    assert session.log_entries == []
    assert Path(session.bin_path).read_bytes() == original


def test_late_range_bounds_failure_rolls_back_in_memory(tmp_path):
    session, original = make_case(tmp_path)
    with pytest.raises(IndexError):
        session.write_table_range(session.tables[0], range(1, 4), range(1, 2), 10.0)
    assert_unchanged(session, original)


def test_range_revalidation_does_not_compare_rounded_audit_values(tmp_path):
    session, original = make_case(tmp_path, "X*0.00000001+if(A==0;Y*0.00000001;0)", linked=True)
    with pytest.raises(ValueError, match="conversion dependency"):
        session.write_table_range(session.tables[0], range(1, 3), range(1, 2), 0.0000001)
    assert_unchanged(session, original)


def test_interrupted_range_restores_memory_and_audit(tmp_path, monkeypatch):
    session, original = make_case(tmp_path)
    original_write = session.write_table_cell

    def interrupted(table, row, col, value, raw_mode=False):
        if row == 2:
            raise KeyboardInterrupt
        return original_write(table, row, col, value, raw_mode)

    monkeypatch.setattr(session, "write_table_cell", interrupted)
    with pytest.raises(KeyboardInterrupt):
        session.write_table_range(session.tables[0], range(1, 3), range(1, 2), 10.0)
    assert_unchanged(session, original)


def test_empty_range_is_refused_without_mutation(tmp_path):
    session, original = make_case(tmp_path)
    with pytest.raises(ValueError, match="at least one cell"):
        session.write_table_range(session.tables[0], range(1, 1), range(1, 2), 10.0)
    assert_unchanged(session, original)


def test_successful_range_save_preserves_other_bytes_and_reports_actual_values(tmp_path):
    session, original = make_case(tmp_path, "X*0.5+1")
    changes = session.write_table_range(session.tables[0], range(1, 3), range(1, 2), 7.3)
    expected = bytearray(original)
    expected[TABLE:TABLE + 2] = bytes([13, 13])
    assert session.bin_data == expected
    assert [change["new_real"] for change in changes] == [7.5, 7.5]
    session.add_table_log_entry("Table")
    binary, log = session.save_final(str(tmp_path / "output"))
    assert Path(binary).read_bytes() == expected
    with Path(log.replace(".log", "_detailed.csv")).open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    assert [float(row["NEW_REAL"]) for row in rows] == [7.5, 7.5]
    assert Path(session.bin_path).read_bytes() == original


@pytest.mark.parametrize("kind", ["scalar", "table"])
def test_unstable_affine_inverse_is_refused_without_mutation(tmp_path, kind):
    session, original = make_case(tmp_path, "(X+1e16)-1e16+0.1*X")
    with pytest.raises(ValueError, match="closer"):
        write_item(session, kind, 2.8)
    assert_unchanged(session, original)


@pytest.mark.parametrize("kind", ["scalar", "table"])
@pytest.mark.parametrize(("equation", "requested", "expected"), [
    ("X*0.5+1", 2.25, 2),
    ("X*0.5+1", 2.75, 4),
    ("10-X*0.5", 8.75, 2),
    ("10-X*0.5", 8.25, 4),
])
def test_stable_half_step_quantization_keeps_ties_to_even(tmp_path, kind, equation, requested, expected):
    session, original = make_case(tmp_path, equation)
    change = write_item(session, kind, requested)
    expected_bytes = bytearray(original)
    expected_bytes[SCALAR if kind == "scalar" else TABLE] = expected
    assert session.bin_data == expected_bytes
    assert change["new_raw"] == expected
    assert Path(session.bin_path).read_bytes() == original


@pytest.mark.parametrize("kind", ["scalar", "table"])
@pytest.mark.parametrize("requested", [-0.4, 2.5, 255.4])
def test_fractional_raw_input_is_explicitly_rejected(tmp_path, kind, requested):
    session, original = make_case(tmp_path)
    with pytest.raises(ValueError, match="integer"):
        write_item(session, kind, requested, raw=True)
    assert_unchanged(session, original)


@pytest.mark.parametrize("kind", ["scalar", "table"])
@pytest.mark.parametrize("requested", [0.0, 2.0, 255.0])
def test_integral_raw_input_still_changes_only_selected_byte(tmp_path, kind, requested):
    session, original = make_case(tmp_path)
    change = write_item(session, kind, requested, raw=True)
    expected = bytearray(original)
    expected[SCALAR if kind == "scalar" else TABLE] = int(requested)
    assert session.bin_data == expected
    assert change["new_raw"] == int(requested)
    assert Path(session.bin_path).read_bytes() == original

"""Regression tests for optional TunerPro XDF attribution in BIN diffs."""

from types import SimpleNamespace

from cli_map_editor import XDFBinSession, _attribute_xdf_differences, cmd_diff


def attributed_session():
    session = XDFBinSession("unused.xdf", "unused.bin")
    session.exporter.base_offset = 8
    session.exporter.base_subtract = 0
    session.exporter.elements = {
        "tables": [{
            "title": "Overlapping map",
            "uniqueid": "0x10",
            "axes": {"z": {
                "address": 0,
                "size_bits": 8,
                "row_count": 2,
                "col_count": 2,
                "major_stride": 0,
                "minor_stride": 0,
            }},
        }],
        "constants": [{
            "title": "Overlapping scalar",
            "uniqueid": "0x20",
            "address": 2,
            "size": 16,
        }],
        "flags": [{
            "title": "Overlapping flag",
            "address": 3,
            "mask": 1,
        }],
        "patches": [{
            "title": "Known patch",
            "entries": [{"name": "Patch code", "address": 4, "datasize": 2}],
        }],
    }
    return session


def test_xdf_attribution_retains_overlaps_cells_and_unmapped_bytes():
    owners, warnings = _attribute_xdf_differences(attributed_session(), {8, 10, 11, 12, 14})

    assert warnings == []
    assert [(item["kind"], item.get("cell")) for item in owners[8]] == [("table", (1, 1))]
    assert {(item["kind"], item.get("cell")) for item in owners[10]} == {
        ("table", (2, 1)),
        ("scalar", None),
    }
    assert {(item["kind"], item.get("cell")) for item in owners[11]} == {
        ("table", (2, 2)),
        ("scalar", None),
        ("flag", None),
    }
    assert [(item["kind"], item.get("entry")) for item in owners[12]] == [
        ("patch", "Patch code")
    ]
    assert 14 not in owners


def test_byte_only_diff_still_works_without_an_xdf_attribute(tmp_path, capsys):
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(bytes([0, 1, 2]))
    second.write_bytes(bytes([0, 9, 2]))

    status = cmd_diff(SimpleNamespace(bin_a=str(first), bin_b=str(second)))
    output = capsys.readouterr().out

    assert status == 0
    assert "Changed bytes: 1" in output
    assert "0x00000001" in output
    assert "TunerPro XDF attribution" not in output

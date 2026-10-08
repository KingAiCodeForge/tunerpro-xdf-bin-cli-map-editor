"""Regression tests for optional TunerPro XDF attribution in BIN diffs."""

from types import SimpleNamespace
import csv
import hashlib
import json

import pytest

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


def report_inputs(tmp_path):
    first, second = tmp_path / "first.bin", tmp_path / "second.bin"
    first.write_bytes(bytes([0, 1, 2]))
    second.write_bytes(bytes([0, 9, 2]))
    return first, second


def test_machine_reports_record_source_hashes_and_all_changed_bytes(tmp_path):
    first, second = report_inputs(tmp_path)
    json_out, csv_out = tmp_path / "diff.json", tmp_path / "diff.csv"
    assert cmd_diff(SimpleNamespace(bin_a=str(first), bin_b=str(second),
                                   json_out=str(json_out), csv_out=str(csv_out))) == 0
    text = json_out.read_text(encoding="utf-8")
    report = json.loads(text)
    assert isinstance(report, dict)
    assert report["bin_a"]["sha256"].lower() == hashlib.sha256(first.read_bytes()).hexdigest()
    assert report["bin_b"]["sha256"].lower() == hashlib.sha256(second.read_bytes()).hexdigest()
    with csv_out.open(encoding="utf-8-sig", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 1


def test_explicit_size_mismatch_reports_missing_bytes_as_null(tmp_path):
    first, second = report_inputs(tmp_path)
    second.write_bytes(first.read_bytes() + b"\x03")
    report = tmp_path / "tail.json"
    assert cmd_diff(SimpleNamespace(bin_a=str(first), bin_b=str(second),
                                   allow_size_mismatch=True, json_out=str(report))) == 0
    text = report.read_text(encoding="utf-8")
    assert "null" in text
    assert isinstance(json.loads(text), dict)


@pytest.mark.parametrize("existing_kind", ["json_out", "csv_out"])
def test_existing_report_is_preserved_and_other_report_is_not_created(tmp_path, existing_kind):
    first, second = report_inputs(tmp_path)
    outputs = {"json_out": tmp_path / "diff.json", "csv_out": tmp_path / "diff.csv"}
    outputs[existing_kind].write_bytes(b"preserve")
    args = SimpleNamespace(bin_a=str(first), bin_b=str(second),
                           **{key: str(path) for key, path in outputs.items()})
    assert cmd_diff(args) == 1
    assert outputs[existing_kind].read_bytes() == b"preserve"
    other_kind = "csv_out" if existing_kind == "json_out" else "json_out"
    assert not outputs[other_kind].exists()


def test_report_aliases_and_duplicate_report_targets_are_rejected(tmp_path):
    first, second = report_inputs(tmp_path)
    before = first.read_bytes()
    assert cmd_diff(SimpleNamespace(bin_a=str(first), bin_b=str(second), json_out=str(first))) == 1
    assert first.read_bytes() == before
    report = tmp_path / "same.txt"
    assert cmd_diff(SimpleNamespace(bin_a=str(first), bin_b=str(second),
                                   json_out=str(report), csv_out=str(report))) == 1
    assert not report.exists()


def test_flag_attribution_requires_its_masked_bits_to_change():
    owners, warnings = _attribute_xdf_differences(attributed_session(), {11}, {11: (1, 3)})
    assert warnings == []
    assert {item["kind"] for item in owners[11]} == {"table", "scalar"}

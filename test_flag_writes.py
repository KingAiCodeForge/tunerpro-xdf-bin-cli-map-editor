"""Regressions for XDF flag writes and project-owned audit provenance."""

import pytest

from cli_map_editor import XDFBinSession, _parse_flag_state


def session(first_byte=0x80):
    data = bytes([first_byte] + [0] * 63)
    result = XDFBinSession("unused.xdf", "unused.bin")
    result.bin_data = bytearray(data)
    result.exporter.bin_data = data
    result.exporter.bin_size = len(data)
    return result


def flag(mask=0x01):
    return {"title": "Test flag", "address": 0, "mask": mask}


def test_set_and_clear_preserve_every_sibling_bit():
    result = session()
    result.write_flag(flag(), True)
    assert result.read_flag_state(flag()) == (0x81, True)
    result.write_flag(flag(), False)
    assert result.read_flag_state(flag()) == (0x80, False)


def test_only_selected_mask_changes():
    result = session(0x99)
    result.write_flag(flag(0x08), False)
    assert result.bin_data[0] == 0x91
    result.write_flag(flag(0x02), True)
    assert result.bin_data[0] == 0x93


@pytest.mark.parametrize("mask", [0, -1, 0x100, "1"])
def test_invalid_mask_is_refused_without_mutation(mask):
    result = session()
    before = bytes(result.bin_data)
    with pytest.raises(ValueError, match="invalid mask"):
        result.write_flag(flag(mask), True)
    assert bytes(result.bin_data) == before


@pytest.mark.parametrize(
    "text,expected",
    [
        ("set", True),
        ("ON", True),
        ("1", True),
        ("clear", False),
        ("Off", False),
        ("0", False),
    ],
)
def test_state_parser_requires_explicit_supported_words(text, expected):
    assert _parse_flag_state(text) is expected


def test_state_parser_rejects_ambiguous_input():
    with pytest.raises(ValueError, match="Invalid flag state"):
        _parse_flag_state("maybe")


def test_audit_log_identifies_its_actual_generator(tmp_path):
    result = session()
    result.bin_path = "example.bin"
    output = tmp_path / "example.log"
    result._write_log(str(output))
    contents = output.read_text(encoding="utf-8")
    assert contents.startswith("KingAI CLI Map Editor audit log for example.bin.\n")
    assert "this is not a native TunerPro log" in contents
    assert "created by TunerPro" not in contents

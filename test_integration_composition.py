"""Keep independently authored features present in the combined alpha source."""
import ast
from pathlib import Path
import re
import sys

import cli_map_editor as editor
import checksum_repair_copy as checksum
import raw_patch_checksum_profiles as profiles


ROOT = Path(__file__).parent


def test_distribution_and_cli_version_agree():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"$', metadata, re.M).group(1)
    assert version == editor.__version__ == "1.3.0a1"


def test_packaging_preserves_all_implemented_modules_and_entrypoints():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    modules = ast.literal_eval(re.search(r'^py-modules = (.+)$', metadata, re.M).group(1))
    assert len(modules) == len(set(modules))
    assert {"transactional_batch", "batch_plan_snapshot", "batch_readback",
            "mock_hardware_adapter", "checksum_repair_copy"}.issubset(modules)
    assert all("extensions" not in name for name in modules)
    assert 'kingai-map-editor = "cli_map_editor:main"' in metadata
    assert 'kingai-checksum-copy = "checksum_repair_copy:main"' in metadata


def test_canonical_cli_advertises_batch_and_both_mock_commands(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["kingai-map-editor", "--help"])
    try:
        editor.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("argparse help did not exit")
    output = capsys.readouterr().out
    for name in ("batch", "adapter-probe", "adapter-preview"):
        assert name in output


def test_checksum_uses_actual_trusted_verifier_not_test_mirror():
    assert (checksum.verify_holden_vy_060a_92118883_additive16
            is profiles.verify_holden_vy_060a_92118883_additive16)
    assert checksum.VY_PROFILE_ID == profiles.VY_PROFILE_ID

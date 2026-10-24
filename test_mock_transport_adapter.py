"""Deterministic, stdlib-only qualification for the synthetic adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from extensions import mock_transport_adapter as adapter


class MockTransportAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "fixture.bin"
        self.bytes = bytes(range(256)) * 2
        self.source.write_bytes(self.bytes)
        self.sha = hashlib.sha256(self.bytes).hexdigest()
        self.original_names = {p.name for p in self.root.iterdir()}

    def preview(self, **options):
        args = dict(path=self.source, expected_sha256=self.sha,
                    expected_size=len(self.bytes), bus_width=8, scenario="ok")
        args.update(options)
        return adapter.preview_upload(**args)

    def test_probe_is_synthetic_and_hash_stable(self):
        first = adapter.probe_mock()
        self.assertEqual(first, adapter.probe_mock())
        self.assertTrue(adapter.validate_receipt(first))
        self.assertEqual(first["evidence"]["qualified_ecu_ids"], [])
        self.assertEqual(first["evidence"]["declared_capabilities"],
                         ["probe_mock", "preview_upload"])
        self.assertFalse(first["device_connected"])
        self.assertFalse(first["flash_eligible"])

    def test_valid_preview_is_deterministic_and_read_only(self):
        first = self.preview()
        self.assertEqual(first, self.preview())
        self.assertEqual(first["decision"], "SIMULATED")
        self.assertEqual(first["code"], "PREVIEW_ONLY")
        self.assertTrue(adapter.validate_receipt(first))
        self.assertEqual(first["evidence"]["source_sha256"], self.sha)
        self.assertEqual(first["hardware_writes"], 0)
        self.assertEqual(first["file_writes"], 0)
        self.assertEqual(self.source.read_bytes(), self.bytes)
        self.assertEqual({p.name for p in self.root.iterdir()}, self.original_names)

    def test_uppercase_hash_is_supported(self):
        self.assertEqual(self.preview(expected_sha256=self.sha.upper())["decision"],
                         "SIMULATED")

    def test_invalid_hash(self):
        self.assertEqual(self.preview(expected_sha256="x")["code"], "HASH_INVALID")
        self.assertEqual(self.preview(expected_sha256=self.sha[:-1] + "z")["code"],
                         "HASH_INVALID")

    def test_mismatched_hash(self):
        self.assertEqual(self.preview(expected_sha256="0" * 64)["code"],
                         "HASH_MISMATCH")

    def test_bad_file_size(self):
        self.assertEqual(self.preview(expected_size=len(self.bytes) + 1)["code"],
                         "SIZE_MISMATCH")
        for value in (0, -1, 16 * 1024 * 1024 + 1, True):
            with self.subTest(value=value):
                self.assertEqual(self.preview(expected_size=value)["code"],
                                 "SIZE_INVALID")

    def test_unsupported_memory_bus(self):
        self.assertEqual(self.preview(bus_width=16)["code"], "BUS_WIDTH_UNSUPPORTED")
        self.assertEqual(self.preview(bus_width=True)["code"], "BUS_WIDTH_UNSUPPORTED")

    def test_missing_and_nonregular_source(self):
        self.assertEqual(self.preview(path=self.root / "absent.bin")["code"],
                         "FILE_UNAVAILABLE")
        self.assertEqual(self.preview(path=self.root)["code"], "NOT_REGULAR")

    def test_symlink_is_refused_when_available(self):
        link = self.root / "alias.bin"
        try:
            link.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not available")
        self.assertEqual(self.preview(path=link)["code"], "LINK_REFUSED")

    def test_truncated_source_is_refused(self):
        self.source.write_bytes(self.bytes[:128])
        self.assertEqual(self.preview()["code"], "SIZE_MISMATCH")

    def test_injected_file_race_is_refused(self):
        with mock.patch.object(adapter, "_same_file", return_value=False):
            self.assertEqual(self.preview()["code"], "SOURCE_CHANGED")

    def test_all_negative_transport_scenarios_refuse(self):
        for scenario in adapter.SCENARIOS:
            if scenario == "ok":
                continue
            with self.subTest(scenario=scenario):
                receipt = self.preview(scenario=scenario)
                self.assertEqual(receipt["decision"], "REFUSED")
                self.assertTrue(adapter.validate_receipt(receipt))
                self.assertEqual(receipt["hardware_writes"], 0)
                self.assertEqual(adapter.probe_mock(scenario)["decision"], "REFUSED")

    def test_unknown_scenario_fails_closed(self):
        self.assertEqual(self.preview(scenario="fictional")["code"],
                         "SCENARIO_INVALID")

    def test_receipt_tampering_is_detected(self):
        receipt = self.preview()
        receipt["flash_eligible"] = True
        self.assertFalse(adapter.validate_receipt(receipt))

    def test_cli_is_machine_json_and_disables_hardware_commands(self):
        for operation in ("flash", "erase"):
            with self.subTest(operation=operation):
                result = subprocess.run(
                    [sys.executable, "-m", "extensions.mock_transport_adapter", operation],
                    capture_output=True, text=True, check=False,
                )
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(payload["code"], "HARDWARE_WRITE_DISABLED")
                self.assertTrue(adapter.validate_receipt(payload))
                self.assertFalse(payload["device_connected"])

    def test_cli_preview_exit_status_and_json_receipt(self):
        cmd = [sys.executable, "-m", "extensions.mock_transport_adapter",
               "preview-upload", "--bin", str(self.source),
               "--expected-sha256", self.sha, "--expected-size", "512"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(adapter.validate_receipt(json.loads(result.stdout)))
        denied = subprocess.run(cmd[:-1] + ["513"], capture_output=True,
                                text=True, check=False)
        self.assertEqual(denied.returncode, 2)
        self.assertEqual(json.loads(denied.stdout)["code"], "SIZE_MISMATCH")

    def test_cli_missing_inputs_refused_as_json(self):
        result = subprocess.run(
            [sys.executable, "-m", "extensions.mock_transport_adapter", "preview-upload"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["code"], "REQUIRED_INPUT_MISSING")


if __name__ == "__main__":
    unittest.main()

"""Assertion-optimization-safe checks for mock adapter source/hash/receipt rules."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from mock_hardware_adapter import (
    AdapterRefusal, MockReadOnlyAdapter, get_adapter,
    write_receipt_exclusive,
)


class AdapterStrictnessTest(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.image = self.root / 'mock image.bin'
        self.data = bytes(range(128))
        self.image.write_bytes(self.data)
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.adapter = MockReadOnlyAdapter()

    def _preview(self, digest=None):
        return self.adapter.preview_image(
            self.image, expected_sha256=digest or self.digest,
            expected_size=len(self.data), declared_target_id='test-ecu.mock',
        )

    def test_no_real_device_capability(self):
        details = self.adapter.probe()
        self.assertFalse(details['hardware_connected'])
        self.assertFalse(details['hardware_writes_supported'])
        self.assertFalse(details['external_dll_loaded'])

    def test_receipt_is_deterministic_and_not_device_proof(self):
        first, second = self._preview(), self._preview()
        self.assertEqual(first, second)
        self.assertFalse(first['hardware_write_executed'])
        self.assertFalse(first['target_identity_verified_on_hardware'])
        self.assertEqual(self.image.read_bytes(), self.data)

    def test_wrong_source_fails_no_written_receipt(self):
        with self.assertRaisesRegex(AdapterRefusal, 'SHA-256 mismatch'):
            self._preview(digest='f' * 64)
        self.assertEqual(sorted(self.root.iterdir()), [self.image])
        with self.assertRaises(AdapterRefusal):
            get_adapter('vendor.dll-loader')

    def test_exclusive_receipt_no_alias_and_no_overwrite(self):
        packet = self._preview()
        with self.assertRaises(AdapterRefusal):
            write_receipt_exclusive(self.image, self.image, packet)
        output = self.root / 'new receipt.json'
        write_receipt_exclusive(output, self.image, packet)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')), packet)
        with self.assertRaises(AdapterRefusal):
            write_receipt_exclusive(output, self.image, packet)
        self.assertEqual(self.image.read_bytes(), self.data)


if __name__ == '__main__':
    unittest.main()

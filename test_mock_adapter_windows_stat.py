"""Cross-API Windows timestamp differences are not actual input mutation."""

import hashlib
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

import mock_hardware_adapter as adapter


class AdapterStatCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        self.image = Path(self.work.name) / "unchanged-synthetic.bin"
        self.data = bytes(range(128))
        self.image.write_bytes(self.data)
        self.digest = hashlib.sha256(self.data).hexdigest()
        self.source_stat = self.image.stat()

    def info(self, *, ctime, **overrides):
        values = {name: getattr(self.source_stat, name) for name in (
            "st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns"
        )}
        values["st_ctime_ns"] = ctime
        values.update(overrides)
        return SimpleNamespace(**values)

    def preview_with_stats(self, path_before, fd_before, fd_after, path_after):
        with mock.patch.object(Path, "stat", side_effect=[path_before, path_after]), \
             mock.patch.object(os, "fstat", side_effect=[fd_before, fd_after]):
            return adapter.MockReadOnlyAdapter().preview_image(
                self.image, expected_sha256=self.digest,
                expected_size=len(self.data), declared_target_id="synthetic",
            )

    def test_stable_different_path_and_fd_ctime_is_not_mutation(self):
        path_info = self.info(ctime=100)
        fd_info = self.info(ctime=200)
        packet = self.preview_with_stats(path_info, fd_info, fd_info, path_info)
        self.assertEqual(packet["source_image"]["sha256"], self.digest.upper())
        self.assertTrue(packet["source_image"]["identity_stable_during_read"])
        self.assertFalse(packet["hardware_write_executed"])
        self.assertEqual(self.image.read_bytes(), self.data)

    def test_path_only_ctime_drift_still_refuses(self):
        path_info = self.info(ctime=100)
        fd_info = self.info(ctime=200)
        with self.assertRaisesRegex(adapter.AdapterRefusal, "changed during read"):
            self.preview_with_stats(path_info, fd_info, fd_info, self.info(ctime=101))

    def test_descriptor_only_ctime_drift_still_refuses(self):
        path_info = self.info(ctime=100)
        fd_info = self.info(ctime=200)
        with self.assertRaisesRegex(adapter.AdapterRefusal, "changed during read"):
            self.preview_with_stats(path_info, fd_info, self.info(ctime=201), path_info)

    def test_cross_api_identity_mismatches_still_refuse(self):
        path_info = self.info(ctime=100)
        for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns"):
            with self.subTest(field=field):
                fd_info = self.info(ctime=200, **{field: getattr(path_info, field) + 1})
                with self.assertRaisesRegex(adapter.AdapterRefusal, "before its read began"):
                    self.preview_with_stats(path_info, fd_info, fd_info, path_info)

    def test_replaced_final_path_still_refuses(self):
        path_info = self.info(ctime=100)
        fd_info = self.info(ctime=200)
        replacement = self.info(ctime=100, st_ino=path_info.st_ino + 1)
        with self.assertRaisesRegex(adapter.AdapterRefusal, "changed during read"):
            self.preview_with_stats(path_info, fd_info, fd_info, replacement)


if __name__ == "__main__":
    unittest.main()

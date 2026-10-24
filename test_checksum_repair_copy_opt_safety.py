"""Optimization-safe bounded checks: unittest rather than bare pytest assert."""
import hashlib
from pathlib import Path
import tempfile
import unittest

from checksum_repair_copy import ChecksumRepairCopyError, plan_repair_copy, write_repair_package
from raw_patch_checksum_profiles import VY_IMAGE_SIZE, VY_OSID_OFFSET, VY_OSID, VY_PROGRAM_ID_OFFSET


def source():
    image=bytearray((i*5+1)&255 for i in range(VY_IMAGE_SIZE))
    image[VY_OSID_OFFSET:VY_OSID_OFFSET+4]=VY_OSID.to_bytes(4,'big')
    image[VY_PROGRAM_ID_OFFSET]=0xAA
    image[0x4006:0x4008]=b'\0\0'
    return bytes(image)


class OptimizedTests(unittest.TestCase):
    def test_full_copy_and_offset_restrictions(self):
        data=source(); h=hashlib.sha256(data).hexdigest()
        repaired,report=plan_repair_copy(data,expected_sha256=h)
        self.assertEqual(report['source_sha256'],h)
        self.assertEqual(report['after']['valid'],True)
        self.assertTrue(set(report['changed_offsets']) <= {'0x04006','0x04007'})
        self.assertEqual(repaired[0x4008],data[0x4008])
        self.assertFalse(report['gate']['ecu_checksum_enforcement_enabled'])
        self.assertNotEqual(repaired,data)

    def test_wrong_hash_refused_under_optimization(self):
        with self.assertRaisesRegex(ChecksumRepairCopyError,'SHA-256 mismatch'):
            plan_repair_copy(source(),expected_sha256='0'*64)

    def test_wrong_gate_refused_under_optimization(self):
        data=bytearray(source());data[0x4008]=0x06
        with self.assertRaisesRegex(ChecksumRepairCopyError,'checksum-gate'):
            plan_repair_copy(bytes(data),expected_sha256=hashlib.sha256(data).hexdigest())

    def test_write_to_new_folder_only(self):
        data=source();h=hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'source.bin';original.write_bytes(data)
            target=Path(tmp)/'target'
            write_repair_package(original,target,expected_sha256=h)
            self.assertEqual(original.read_bytes(),data)
            self.assertTrue((target/'source.checksum-copy.bin').exists())
            self.assertTrue((target/'receipt.json').exists())
            with self.assertRaises(FileExistsError):
                write_repair_package(original,target,expected_sha256=h)


if __name__=='__main__':unittest.main()

"""Optimization-safe bounded checks: unittest rather than bare pytest assert."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import checksum_repair_copy as adapter
from checksum_repair_copy import ChecksumRepairCopyError, plan_repair_copy, write_repair_package
from raw_patch_checksum_profiles import (
    VY_IMAGE_SIZE, VY_OSID_OFFSET, VY_OSID, VY_PROGRAM_ID_OFFSET,
    verify_holden_vy_060a_92118883_additive16 as actual_verify,
)


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

    def test_actual_verifier_context_phases(self):
        data=source();phases=[]
        def verify(image,context):
            phases.append(context['phase'])
            return actual_verify(image,context)
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'source.bin';original.write_bytes(data)
            with patch.object(adapter,'verify_holden_vy_060a_92118883_additive16',verify):
                write_repair_package(original,Path(tmp)/'out',expected_sha256=hashlib.sha256(data).hexdigest())
        self.assertEqual(phases,['input','output','output'])

    def test_final_verifier_mutation_never_publishes_receipt(self):
        for victim in ('source','output'):
            with self.subTest(victim=victim),tempfile.TemporaryDirectory() as tmp:
                data=source();original=Path(tmp)/'source.bin';original.write_bytes(data)
                output=Path(tmp)/'out';calls=[]
                def verify(image,context):
                    calls.append(context['phase'])
                    result=actual_verify(image,context)
                    if len(calls)==3:
                        target=original if victim=='source' else output/'source.checksum-copy.bin'
                        altered=bytearray(target.read_bytes());altered[0x2000]^=1
                        target.write_bytes(altered)
                    return result
                with patch.object(adapter,'verify_holden_vy_060a_92118883_additive16',verify):
                    with self.assertRaisesRegex(ChecksumRepairCopyError,'before receipt publication'):
                        write_repair_package(original,output,expected_sha256=hashlib.sha256(data).hexdigest())
                self.assertFalse((output/'receipt.json').exists())

    def test_partial_receipt_failure_is_not_final(self):
        data=source()
        def fail(value,stream,**kwargs):
            stream.write('{')
            raise OSError('partial receipt')
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'source.bin';original.write_bytes(data)
            output=Path(tmp)/'out'
            with patch.object(adapter.json,'dump',fail):
                with self.assertRaisesRegex(OSError,'partial receipt'):
                    write_repair_package(original,output,expected_sha256=hashlib.sha256(data).hexdigest())
            self.assertFalse((output/'receipt.json').exists())
            self.assertEqual(original.read_bytes(),data)

    def test_receipt_collision_preserved(self):
        data=source();actual_link=adapter.os.link
        def collide(pending,final):
            Path(final).write_bytes(b'preserve collision')
            return actual_link(pending,final)
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'source.bin';original.write_bytes(data)
            output=Path(tmp)/'out'
            with patch.object(adapter.os,'link',collide):
                with self.assertRaises(FileExistsError):
                    write_repair_package(original,output,expected_sha256=hashlib.sha256(data).hexdigest())
            self.assertEqual((output/'receipt.json').read_bytes(),b'preserve collision')
            self.assertEqual(original.read_bytes(),data)


if __name__=='__main__':unittest.main()

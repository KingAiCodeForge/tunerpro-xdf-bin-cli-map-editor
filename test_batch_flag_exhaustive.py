"""Exhaustive read-only two-bit flag matrix over every containing-byte value."""
import contextlib
import csv
import io
from pathlib import Path

from transactional_batch import run_batch
from test_transactional_batch_unit import FakeSession, setup, ranges, state


def test_all_256_original_bytes_and_4_two_flag_outcomes(tmp_path):
    args, original = setup(tmp_path, [
        ('flag', 'Feature A', '', '', 'set', ''),
        ('flag', 'Feature B', '', '', 'set', ''),
    ], autosave=False)
    plan = Path(args.csv)
    def choices(a,b):
        with plan.open('w', encoding='utf-8', newline='') as handle:
            writer=csv.writer(handle)
            writer.writerow(['type','map','row','col','value','raw'])
            writer.writerows([
                ('flag','Feature A','','','set' if a else 'clear',''),
                ('flag','Feature B','','','set' if b else 'clear',''),
            ])
    output=io.StringIO()
    for a in (False, True):
        for b in (False, True):
            choices(a,b)
            for original_byte in range(256):
                before = bytearray(original.read_bytes())
                before[48] = original_byte
                original.write_bytes(before)
                with contextlib.redirect_stdout(output):
                    assert run_batch(args, FakeSession, ranges, state)==0
                after=bytes(FakeSession.last.bin_data)
                expected=(original_byte & ~0x03) | (int(a)<<0) | (int(b)<<1)
                assert after[48] == expected, (a,b,original_byte,expected,after[48])
                assert after[:48] == bytes(before[:48])
                assert after[49:] == bytes(before[49:])
                assert original.read_bytes() == bytes(before)
                assert len(FakeSession.last.changes)==2
                output.seek(0);output.truncate(0)
    assert not (tmp_path/'out').exists()

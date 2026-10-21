"""Additional local hardening regressions for the dependency-free batch engine."""
import csv
import hashlib
from pathlib import Path

import pytest
import transactional_batch as batch
from test_transactional_batch_unit import FakeSession, setup, run, ranges, state


def _plan_with_expected(tmp_path, rows):
    args, original = setup(tmp_path, [], autosave=True)
    with Path(args.csv).open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['type', 'map', 'row', 'col', 'value', 'raw', 'expected_raw'])
        writer.writerows(rows)
    return args, original


def test_good_exact_old_raw_across_three_object_kinds_and_receipt_plan_hash(tmp_path, capsys):
    args, original = _plan_with_expected(tmp_path, [
        ('scalar', 'MAP Linear', '', '', '3', '', '0x2'),
        ('table', 'Ignition', '1', '1', '36', '', '0'),
        ('flag', 'Feature A', '', '', 'set', '', '0x00'),
        ('flag', 'Feature B', '', '', 'set', '', '0x01'),
    ])
    # The flag precondition on the second flag must see staged state (0x01).
    args.json = True
    assert run(args) == 0
    import json
    receipt=json.loads(capsys.readouterr().out)
    assert receipt['plan']['sha256'] == hashlib.sha256(Path(args.csv).read_bytes()).hexdigest()
    assert (tmp_path / 'out' / 'source_batch.bin').read_bytes()[48] == 0x03
    assert original.read_bytes()[48] == 0


@pytest.mark.parametrize('change', ['first_cell', 'second_cell', 'flag', 'scalar'])
def test_expected_old_raw_mismatch_rolls_back_everything(tmp_path, change):
    old = {'first_cell':('table','Ignition','1','1','40','','3'),
           'second_cell':('table','Ignition','1','2','40','','3'),
           'flag':('flag','Feature A','','','set','','1'),
           'scalar':('scalar','MAP Linear','','','3','','9')}[change]
    operations=[('table','Ignition','1','1','40','','0')]
    if change == 'first_cell': operations = [old]
    else: operations.append(old)
    args, original = _plan_with_expected(tmp_path, operations)
    before = original.read_bytes()
    with pytest.raises(ValueError, match='old raw value changed'):
        run(args)
    assert not (tmp_path / 'out').exists()
    assert original.read_bytes() == before
    assert FakeSession.last.changes == []


def test_table_range_requires_old_raw_for_every_cell(tmp_path):
    args, original = _plan_with_expected(tmp_path, [
        ('table','Ignition','1','1-2','40','','1'),
    ])
    with pytest.raises(ValueError, match='old raw value changed'):
        run(args)
    assert FakeSession.last.changes == []
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('expected', ['1.2','foo','0x','01'])
def test_expected_raw_must_be_integral_int_syntax(tmp_path, expected):
    args, original = _plan_with_expected(tmp_path, [
        ('scalar','MAP Linear','','','3','',expected)
    ])
    FakeSession.last=None
    with pytest.raises(ValueError, match='expected_raw must be a signed integer'):
        run(args)
    assert FakeSession.last is None


@pytest.mark.parametrize('remaining', [1, 2])
def test_partial_multibit_flag_clear_refused_even_when_boolean_false(tmp_path, remaining):
    args, original = setup(tmp_path, [
        ('flag','Feature A','','','clear',''),
    ], autosave=True)
    image = bytearray(original.read_bytes()); image[48] = 0x03; original.write_bytes(image)

    class BrokenFlagSession(FakeSession):
        def __init__(self,*a):
            super().__init__(*a)
            self.flags[0]['mask'] = 0x03
        def write_flag(self, flag, new_state):
            rec = super().write_flag(flag, new_state)
            self.bin_data[48] = remaining
            return rec

    with pytest.raises(ValueError, match='incomplete flag mask write'):
        batch.run_batch(args, BrokenFlagSession, ranges, state)
    assert original.read_bytes() == bytes(image)
    assert not (tmp_path/'out').exists()
    assert FakeSession.last.changes == []


def test_plan_mutation_during_session_load_is_detected(tmp_path):
    args, original = setup(tmp_path,[('scalar','MAP Linear','','','3',False)],True)

    class RewritePlanDuringLoad(FakeSession):
        def load(self):
            with open(args.csv, 'a', encoding='utf-8') as handle: handle.write('\n')
            return True
    with pytest.raises(ValueError, match='plan changed while loading'):
        batch.run_batch(args, RewritePlanDuringLoad, ranges, state)
    assert not (tmp_path/'out').exists()


def test_plan_mutation_after_staging_refuses_publication(tmp_path, monkeypatch):
    args, original = setup(tmp_path,[('scalar','MAP Linear','','','3',False)],True)
    real_verify = batch._verify_final
    def tamper(*v):
        changes = real_verify(*v)
        with open(args.csv, 'a', encoding='utf-8') as handle: handle.write('\n')
        return changes
    monkeypatch.setattr(batch, '_verify_final', tamper)
    with pytest.raises(ValueError, match='changed while staging'):
        run(args)
    assert not (tmp_path/'out').exists()

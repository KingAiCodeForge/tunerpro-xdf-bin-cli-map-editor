"""Strict AI JSON edit-plan tests without a vehicle image or parser dependency."""
import hashlib
import json
from pathlib import Path

import pytest
from transactional_batch import read_json_plan, run_batch
from test_transactional_batch_unit import FakeSession, setup, ranges, state


def make_plan(tmp_path,ops,corrupt_hash=None):
    args, origin = setup(tmp_path, [],autosave=True)
    doc = {
        'schema':'kingai.xdf-batch-plan.v1',
        'source_bin_sha256':hashlib.sha256(Path(args.bin).read_bytes()).hexdigest(),
        'xdf_sha256':hashlib.sha256(Path(args.xdf).read_bytes()).hexdigest(),
        'operations':ops,
    }
    if corrupt_hash:doc[corrupt_hash]='0'*64
    path=tmp_path/'plan.json';path.write_text(json.dumps(doc),encoding='utf-8')
    args.plan_json=str(path)
    args.csv=None
    return args,origin,path


def execute(args):return run_batch(args, FakeSession, ranges, state)


def test_json_mixed_operations_hash_bound_and_one_output(tmp_path, capsys):
    args, origin, plan=make_plan(tmp_path,[
        {'type':'scalar','map':'MAP Linear','value':3,'expected_raw':2},
        {'type':'table','map':'Ignition','row':1,'col':'1-2','value':30,'expected_raw':0},
        {'type':'flag','map':'Feature A','value':'set','expected_raw':0},
    ])
    args.json=True
    assert execute(args)==0
    report=json.loads(capsys.readouterr().out)
    assert report['plan']['format']=='json'
    assert report['plan_operations']==3
    assert report['csv_rows'] is None
    assert report['changed_byte_count']==4
    assert (tmp_path/'out'/'source_batch.bin').read_bytes()[16:18]==bytes([10,10])
    assert origin.read_bytes()[16:18]==b'\x00\x00'


def test_json_preview_does_not_save(tmp_path,capsys):
    args,origin,plan=make_plan(tmp_path,[{'type':'scalar','map':'MAP Linear','value':5}])
    args.autosave=False;args.output_dir=None;args.json=True
    assert execute(args)==0
    report=json.loads(capsys.readouterr().out)
    assert report['status']=='dry_run'
    assert report['saved_bin'] is None
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('badfield',['source_bin_sha256','xdf_sha256'])
def test_json_wrong_pinned_hash_refused_before_session(tmp_path,badfield):
    args,origin,plan=make_plan(tmp_path,[{'type':'scalar','map':'MAP Linear','value':5}],badfield)
    FakeSession.last=None
    with pytest.raises(ValueError,match='SHA-256 does not match'):
        execute(args)
    assert FakeSession.last is None
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('bad', [
    {'unexpected':'x'},
    {'type':'scalar','map':'MAP Linear','value':3,'raw':{'trick':'true'}},
    {'type':'scalar','map':'MAP Linear','value':True},
    {'type':'scalar','map':'MAP Linear','value':'nan'},
    {'type':'table','map':'Ignition','row':1,'col':1,'value':5,'extra':True},
])
def test_json_bad_operations_rejected_before_session(tmp_path,bad):
    args,origin,plan=make_plan(tmp_path,[bad])
    FakeSession.last=None
    with pytest.raises(ValueError):execute(args)
    assert FakeSession.last is None


def test_json_nan_literal_fails_strict_load(tmp_path):
    args,origin,plan=make_plan(tmp_path,[{'type':'scalar','map':'MAP Linear','value':5}])
    plan.write_text(plan.read_text().replace('"value": 5', '"value": NaN'))
    with pytest.raises(ValueError,match='nonfinite numeric constant'):
        read_json_plan(plan)


def test_json_no_fallback_to_csv_when_both_inputs_present(tmp_path):
    args,origin,plan=make_plan(tmp_path,[{'type':'scalar','map':'MAP Linear','value':5}])
    args.csv=str(tmp_path/'edits.csv')
    with pytest.raises(ValueError,match='exactly one batch input'):execute(args)


def test_json_plan_hash_mutation_rejected(tmp_path):
    args,origin,plan=make_plan(tmp_path,[{'type':'scalar','map':'MAP Linear','value':5}])
    class TamperingSession(FakeSession):
        def load(self):
            plan.write_text(plan.read_text()+' ')
            return True
    with pytest.raises(ValueError,match='plan changed while loading'):
        run_batch(args,TamperingSession,ranges,state)
    assert not (tmp_path/'out').exists()

@pytest.mark.parametrize('duplicate', [
    '"schema": "kingai.xdf-batch-plan.v1",',
    '"source_bin_sha256": "'+'0'*64+'",',
])
def test_json_duplicate_top_level_key_is_rejected(tmp_path, duplicate):
    args, origin, plan = make_plan(tmp_path,[{'type':'scalar','map':'MAP Linear','value':5}])
    body = plan.read_text()
    plan.write_text(body.replace('{', '{'+duplicate, 1))
    with pytest.raises(ValueError, match='Duplicate JSON plan key'):
        read_json_plan(plan)

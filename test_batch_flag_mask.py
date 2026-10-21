"""Flag mask disambiguation with same-title, same-address XDF entries."""
import csv
from pathlib import Path

import pytest
from transactional_batch import read_plan, run_batch, read_json_plan
from test_transactional_batch_unit import FakeSession, setup, ranges, state


class DuplicateFlags(FakeSession):
    selected=[]
    def __init__(self,*a):
        super().__init__(*a)
        self.flags[0]['address']=0x55
        self.flags[0]['mask']=0x01
        self.flags.append({'title':'Feature A','address':0x55,'mask':0x04})
        DuplicateFlags.selected=[]
    def write_flag(self,flag,*a):
        DuplicateFlags.selected.append(flag['mask'])
        return super().write_flag(flag,*a)


def make_csv(tmp_path,flag_mask,other=None):
    args,origin=setup(tmp_path,[],True)
    with Path(args.csv).open('w',encoding='utf-8',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['type','map','row','col','value','address','flag_mask'])
        kind = other or 'flag'
        writer.writerow([kind,'Feature A','1' if kind=='table' else '',
                         '1' if kind=='table' else '', '5' if kind=='table' else 'set', '0x55', flag_mask])
    return args,origin


def test_select_flag_by_exact_byte_address_and_mask(tmp_path):
    args,origin=make_csv(tmp_path,'0x04')
    assert run_batch(args,DuplicateFlags,ranges,state)==0
    assert DuplicateFlags.selected==[0x04]
    assert (tmp_path/'out'/'source_batch.bin').read_bytes()[48]==4
    assert origin.read_bytes()[48]==0


def test_flag_alias_same_title_same_address_is_ambiguous_without_mask(tmp_path):
    args,origin=make_csv(tmp_path,'')
    with pytest.raises(ValueError,match='ambiguous flag title'):
        run_batch(args,DuplicateFlags,ranges,state)
    assert DuplicateFlags.selected==[]
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('mask',['0','0x100','broken','-2'])
def test_invalid_flag_mask_fails_before_session(tmp_path,mask):
    args,origin=make_csv(tmp_path,mask)
    with pytest.raises(ValueError,match='flag_mask'): read_plan(args.csv)


def test_flag_mask_invalid_for_table(tmp_path):
    args,origin=make_csv(tmp_path,'1','table')
    with pytest.raises(ValueError,match='flag_mask only applies to flags'):
        read_plan(args.csv)


def test_disjoint_same_title_flags_selected_in_single_plan(tmp_path):
    args,origin=setup(tmp_path,[],True)
    with Path(args.csv).open('w',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(['type','map','value','address','flag_mask'])
        writer.writerows([('flag','Feature A','set','0x55','0x1'),
                          ('flag','Feature A','set','0x55','0x4')])
    assert run_batch(args,DuplicateFlags,ranges,state)==0
    assert DuplicateFlags.selected==[1,4]
    assert (tmp_path/'out'/'source_batch.bin').read_bytes()[48]==5

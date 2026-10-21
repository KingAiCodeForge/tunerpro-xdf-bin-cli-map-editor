"""XDF object-selection regressions for ambiguous titles and source addresses."""
import csv
from pathlib import Path

import pytest
from transactional_batch import read_plan, run_batch
from test_transactional_batch_unit import FakeSession, setup, ranges, state


class DuplicateSession(FakeSession):
    selected = []

    def __init__(self, *args):
        super().__init__(*args)
        self.tables[0]['uniqueid'] = '0x01'
        self.tables[0]['axes']['z']['address'] = 0x10
        self.tables.append({'title':'Ignition','uniqueid':'0x02','axes':{'z':{'address':0x20}}})
        self.constants[0]['uniqueid']='0x03'
        self.constants[0]['address']=0x20
        self.constants.append({'title':'MAP Linear','uniqueid':'0x04','address':0x30})
        self.flags[0]['address']=0x30
        self.flags.append({'title':'Feature A','address':0x40,'mask':0x04})
        DuplicateSession.selected=[]

    def write_table_cell(self,item,*args,**kwargs):
        DuplicateSession.selected.append(('table', item.get('uniqueid')))
        return super().write_table_cell(item,*args,**kwargs)

    def write_scalar(self,item,*args,**kwargs):
        DuplicateSession.selected.append(('scalar', item.get('uniqueid')))
        return super().write_scalar(item,*args,**kwargs)

    def write_flag(self,item,*args,**kwargs):
        DuplicateSession.selected.append(('flag', item.get('address')))
        return super().write_flag(item,*args,**kwargs)


def csv_plan(tmp_path, records):
    args, original = setup(tmp_path, [], autosave=True)
    with Path(args.csv).open('w', encoding='utf-8', newline='') as handle:
        writer=csv.writer(handle)
        writer.writerow(['type','map','row','col','value','uniqueid','address'])
        writer.writerows(records)
    return args, original


def run(args): return run_batch(args,DuplicateSession,ranges,state)


@pytest.mark.parametrize('kind,rows', [
    ('table',[('table','Ignition','1','1','40','','')]),
    ('scalar',[('scalar','MAP Linear','','','3','','')]),
    ('flag',[('flag','Feature A','','','set','','')])
])
def test_ambiguous_title_fails_without_first_match(tmp_path,kind,rows):
    args, original=csv_plan(tmp_path,rows)
    with pytest.raises(ValueError,match=f'ambiguous {kind} title'): run(args)
    assert DuplicateSession.selected==[]
    assert not (tmp_path/'out').exists()


def test_exact_uid_selects_duplicate_table_and_scalar_without_title_guessing(tmp_path):
    args, original=csv_plan(tmp_path, [
        ('scalar','MAP Linear','','','3','0x04',''),
        ('table','Ignition','1','1','40','0x02',''),
    ])
    assert run(args)==0
    assert DuplicateSession.selected == [('scalar','0x04'),('table','0x02')]
    assert (tmp_path/'out'/'source_batch.bin').exists()


def test_address_selects_duplicate_flag_and_table(tmp_path):
    args, original=csv_plan(tmp_path, [
        ('table','Ignition','1','1','40','','0x20'),
        ('flag','Feature A','','','set','','0x40'),
    ])
    assert run(args)==0
    assert DuplicateSession.selected == [('table','0x02'),('flag',0x40)]


def test_wrong_uid_or_address_is_not_silently_fallback_to_title(tmp_path):
    for rec in [
        ('scalar','MAP Linear','','','3','missing',''),
        ('table','Ignition','1','1','40','0x01','0x20'),
        ('flag','Feature A','','','set','','0x50'),
    ]:
        args, original=csv_plan(tmp_path,[rec])
        with pytest.raises(ValueError,match='not found'): run(args)
        assert DuplicateSession.selected == []
        assert not (tmp_path/'out').exists()


def test_flag_uid_is_rejected_when_exporter_has_no_uid(tmp_path):
    args, original=csv_plan(tmp_path, [('flag','Feature A','','','set','0xA','0x40')])
    with pytest.raises(ValueError,match='Flag XDF uniqueid is not exposed'): run(args)
    assert DuplicateSession.selected == []


@pytest.mark.parametrize('bad',['-1','0x','1.2','hello'])
def test_bad_xdf_address_selector_rejected_early(tmp_path,bad):
    args, original=csv_plan(tmp_path,[('scalar','MAP Linear','','','3','',''+bad)])
    with pytest.raises(ValueError,match='address'):read_plan(args.csv)

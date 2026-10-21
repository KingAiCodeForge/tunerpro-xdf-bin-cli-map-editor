"""Dependency-free local executable tests of the complete batch coordinator."""
import csv
from pathlib import Path
from types import SimpleNamespace
import pytest
from transactional_batch import run_batch, read_plan


class FakeSession:
    last = None
    def __init__(self, xdf, binfile):
        self.xdf_path, self.bin_path = xdf, binfile
        self.bin_data = bytearray(Path(binfile).read_bytes())
        self.changes = []
        self.log_entries = []
        self.tables = [{'title':'Ignition', 'axes': {'z': {'signed':False, 'lsb_first':False}}}]
        self.constants = [{'title':'MAP Linear', 'signed':False, 'lsb_first':False}]
        self.flags = [{'title':'Feature A','mask':1},{'title':'Feature B','mask':2}, {'title':'Bit alias','mask':1}]
        self.exporter = SimpleNamespace(evaluate_math=lambda eq, raw, linked_vars: (float(raw)*linked_vars["factor"], None))
        FakeSession.last = self
    def load(self): return True
    def find_table(self, name): return next((t for t in self.tables if t['title']==name),None)
    def find_constant(self, name): return next((t for t in self.constants if t['title']==name),None)
    def find_flag(self, name): return next((t for t in self.flags if t['title']==name),None)
    def get_table_dimensions(self,t): return (1,2)
    def _current_variables(self,z,t,row,col): return {"factor": self.bin_data[32]}
    def read_table_data(self,t): return [[float(self.bin_data[16])*self.bin_data[32],float(self.bin_data[17])*self.bin_data[32]]]
    def read_scalar_value(self,c): return self.bin_data[32],float(self.bin_data[32])
    def read_flag_state(self,f): return self.bin_data[48],bool(self.bin_data[48]&f['mask'])
    def _read_raw_at(self,offset,bits,signed=False,lsb=False): assert bits==8; return self.bin_data[offset]
    def write_table_cell(self,t,row,col,value,raw_mode=False):
        if row!=1 or not 1<=col<=2: raise IndexError('Out of table')
        offset=15+col
        old=self.bin_data[offset]
        raw=round(value if raw_mode else value/self.bin_data[32])
        if not 0<=raw<=255: raise ValueError('Raw out of bounds')
        self.bin_data[offset]=raw
        c=dict(type='table',map=t['title'],row=row,col=col,old_raw=old,new_raw=raw,
               old_real=float(old),new_real=float(raw),size_bits=8,unit='degree',file_offset=f'0x{offset:04X}')
        self.changes.append(c);return c
    def write_scalar(self,c,value,raw_mode=False):
        old=self.bin_data[32];raw=int(value)
        if not 0<=raw<=255: raise ValueError('Raw out of bounds')
        self.bin_data[32]=raw
        rec=dict(type='scalar',map=c['title'],row='',col='',old_raw=old,new_raw=raw,
                 old_real=float(old),new_real=float(raw),size_bits=8,unit='',file_offset='0x0020')
        self.changes.append(rec);return rec
    def write_flag(self,f,state):
        old=self.bin_data[48]
        self.bin_data[48]=old|f['mask'] if state else old&~f['mask']
        rec=dict(type='flag',map=f['title'],row='',col='',old_raw=old,new_raw=self.bin_data[48],
                 old_real=bool(old&f['mask']),new_real=state,size_bits=8,unit='mask',file_offset='0x0030')
        self.changes.append(rec);return rec
    def add_table_log_entry(self,name): self.log_entries.append(name)
    def save_final(self,folder,operation):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
        out=folder/f'source_{operation}.bin'
        out.write_bytes(self.bin_data)
        return str(out),'fake_audit.log'


def ranges(text):
    a,b=[int(x) for x in text.split('-')] if '-' in text else (int(text),int(text))
    if a>b: raise ValueError('Invalid range')
    return range(a,b+1)


def state(value):
    if value in {'set','1','on'}: return True
    if value in {'clear','0','off'}: return False
    raise ValueError('Invalid state')


def setup(tmp_path,rows,autosave=False,expected_bin_sha256=None):
    xdf=tmp_path/'a.xdf'; xdf.write_bytes(b'fixture-definition')
    binary=tmp_path/'a.bin';data=bytearray(64);data[32]=2;binary.write_bytes(data)
    plan=tmp_path/'edits.csv'
    with plan.open('w',encoding='utf-8',newline='') as f:
        wr=csv.writer(f);wr.writerow(['type','map','row','col','value','raw']);wr.writerows(rows)
    args=SimpleNamespace(xdf=str(xdf),bin=str(binary),csv=str(plan),default_map=None,
        autosave=autosave,output_dir=str(tmp_path/'out') if autosave else None,
        expected_bin_sha256=expected_bin_sha256,expected_xdf_sha256=None)
    return args, binary


def run(args): return run_batch(args,FakeSession,ranges,state)


def test_multitarget_write_flag_masks_and_autosave(tmp_path):
    rows=[['table','Ignition',1,1,40,False], ['scalar','MAP Linear','','',3,False],
          ['table','Ignition',1,2,60,False],['flag','Feature A','','','set',False],
          ['flag','Feature B','','','set',False]]
    args, binary=setup(tmp_path,rows,True)
    baseline=binary.read_bytes()
    # Scalar change alters the earlier cell's decoded real value: reject before publish.
    with pytest.raises(ValueError,match='conversion dependency changed'):
        run(args)
    assert not (tmp_path/'out').exists()
    assert binary.read_bytes()==baseline
    assert FakeSession.last.changes == []
    # Reorder scalar before tables and revalidate the same targets.
    args,binary=setup(tmp_path,[rows[1],rows[0],rows[2],rows[3],rows[4]],True)
    assert run(args)==0
    saved=(tmp_path/'out'/'source_batch.bin').read_bytes()
    assert saved[16:18]==b'\r\x14' and saved[32]==3 and saved[48]==3
    assert binary.read_bytes()==baseline
    assert len(FakeSession.last.changes)==5
    assert FakeSession.last.log_entries==['Ignition']


def test_preview_does_not_write(tmp_path):
    args,binary=setup(tmp_path,[['table','Ignition',1,'1-2',30,False],
                                  ['flag','Feature A','','','set',False]])
    before=binary.read_bytes()
    assert run(args)==0
    assert binary.read_bytes()==before
    assert not (tmp_path/'out').exists()


def test_conflicting_same_cell_and_flags_abort(tmp_path):
    for rows in [
        [['table','Ignition',1,1,40,False],['table','Ignition',1,1,40,False]],
        [['flag','Feature A','','','set',False],['flag','Bit alias','','','set',False]],
    ]:
        args,binary=setup(tmp_path,rows,True)
        with pytest.raises(ValueError,match='Conflicting XDF writes'):
            run(args)
        assert binary.read_bytes()[16]==0
        assert FakeSession.last.changes == []
        assert not (tmp_path/'out').exists()


def test_invalid_late_operation_rolls_back_no_files(tmp_path):
    rows=[['table','Ignition',1,1,40,False],['scalar','No such scalar','','',2,False]]
    args,binary=setup(tmp_path,rows,True)
    with pytest.raises(ValueError,match='not found'): run(args)
    assert FakeSession.last.changes == []
    assert FakeSession.last.bin_data == bytearray(binary.read_bytes())
    assert not (tmp_path/'out').exists()


def test_reject_wrong_bin_hash_before_session(tmp_path):
    args,binary=setup(tmp_path,[['scalar','MAP Linear','','',2,False]],True,'0'*64)
    FakeSession.last=None
    with pytest.raises(ValueError,match='SHA-256 does not match'): run(args)
    assert FakeSession.last is None


def test_invalid_csv_fail_before_session(tmp_path):
    args,binary=setup(tmp_path,[['table','Ignition',1,1,'nan',False]],True)
    FakeSession.last=None
    with pytest.raises(ValueError,match='finite'): run(args)
    assert FakeSession.last is None


def test_output_requires_autosave(tmp_path):
    args,binary=setup(tmp_path,[['scalar','MAP Linear','','',3,False]])
    args.output_dir=str(tmp_path/'out')
    with pytest.raises(ValueError,match='without --autosave'): run(args)


def test_read_plan_refuses_extra_columns(tmp_path):
    csv_path=tmp_path/'bad.csv';csv_path.write_text('type,map,value\nscalar,X,2,extra\n')
    with pytest.raises(ValueError,match='excess columns'): read_plan(str(csv_path))


def test_flag_writer_cannot_change_unclaimed_bit(tmp_path):
    args,binary=setup(tmp_path,[['flag','Feature A','','','set',False]],True)
    original=binary.read_bytes()

    class InvalidFlagSession(FakeSession):
        def write_flag(self, flag, state):
            result=super().write_flag(flag,state)
            self.bin_data[48] |= 0x80
            return result

    with pytest.raises(ValueError, match='undeclared bit'):
        run_batch(args, InvalidFlagSession, ranges, state)
    assert binary.read_bytes()==original
    assert not (tmp_path/'out').exists()
    assert FakeSession.last.changes==[]

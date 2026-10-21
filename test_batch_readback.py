"""Staged Exporter selection and per-cell conversion readback regressions."""
from types import SimpleNamespace
import pytest
from batch_readback import decoded_table_cell


class Exporter:
    def __init__(self, original):
        self.bin_data = original
        self.seen=[]
    def _cell_equation_selector(self,z):
        self.seen.append(('selector',self.bin_data[4]))
        def select(r,c):
            return ('X + A + B + Z + Y + k', {'k':self.bin_data[4]}, 'math-raw-alias')
        return select
    def table_context(self,item,r,c):
        self.seen.append(('context',self.bin_data[4]))
        return {'row_index':r,'col_index':c, 'x_axis_value':item['axes']['x'][c], 'y_axis_value':item['axes']['y'][r]}
    def evaluate_math(self, equation, raw, context, *, linked_vars, math_element):
        assert math_element == 'math-raw-alias'
        assert equation == 'X + A + B + Z + Y + k'
        return (raw + context['row_index'] + context['col_index']
                + context['x_axis_value'] + context['y_axis_value'] + linked_vars['k']),''


def fixture():
    old=bytes([0,0,0,0,3])
    new=bytearray(old);new[4]=6
    exp=Exporter(old)
    session=SimpleNamespace(bin_data=new, exporter=exp)
    item={'axes':{'z':{'equation':'X'}, 'x':[10,20], 'y':[100,200]}}
    return session,item,exp,old


def test_staged_values_axis_context_math_and_old_exporter_restored():
    s,item,exp,old=fixture()
    assert decoded_table_cell(s,item,2,2,7)==7+1+1+20+200+6
    assert exp.seen==[('selector',6),('context',6)]
    assert exp.bin_data is old


def test_value_changes_when_staged_linked_dependency_changes():
    s,item,exp,old=fixture()
    a=decoded_table_cell(s,item,1,1,2)
    s.bin_data[4]=8
    b=decoded_table_cell(s,item,1,1,2)
    assert b-a==2
    assert exp.bin_data is old


@pytest.mark.parametrize('row,col',[(0,1),(1,0),(-1,1),(1,-1),(1.2,1),(True,1)])
def test_bad_indices_fail_closed(row,col):
    s,item,exp,old=fixture()
    with pytest.raises(ValueError,match='positive 1-based'):
        decoded_table_cell(s,item,row,col,1)
    assert exp.bin_data is old


def test_restore_original_when_selector_raises():
    s,item,exp,old=fixture()
    exp._cell_equation_selector=lambda z: (_ for _ in ()).throw(ValueError('bad XDF'))
    with pytest.raises(ValueError,match='bad XDF'):
        decoded_table_cell(s,item,1,1,1)
    assert exp.bin_data is old


def test_reject_missing_table_context_api():
    s,item,exp,old=fixture()
    exp.table_context=None
    with pytest.raises(ValueError,match='lacks a table context resolver'):
        decoded_table_cell(s,item,1,1,1)
    assert exp.bin_data is old


@pytest.mark.parametrize('bad',[None,float('nan'),float('inf'),'7',object()])
def test_non_numeric_or_nonfinite_exporter_result_fail_closed(bad):
    s,item,exp,old=fixture()
    exp.evaluate_math=lambda *a,**kw:(bad,'')
    with pytest.raises(ValueError,match='missing or nonfinite'):
        decoded_table_cell(s,item,1,1,1)
    assert exp.bin_data is old


def test_fallback_remains_compatible_with_dependency_free_sessions():
    exporter=SimpleNamespace(evaluate_math=lambda eq,raw,linked_vars:(raw*linked_vars['factor'],''))
    s=SimpleNamespace(exporter=exporter,_current_variables=lambda z,t,r,c:{'factor':3})
    t={'axes':{'z':{'equation':'X * factor'}}}
    assert decoded_table_cell(s,t,1,2,7)==21


def test_no_fallback_if_selector_exists_but_broken():
    s,item,exp,old=fixture()
    exp.table_context = None
    with pytest.raises(ValueError): decoded_table_cell(s,item,1,1,1)


def test_staged_readback_does_not_copy_large_bin_per_cell():
    class NoBytes(bytearray):
        def __bytes__(self):
            raise AssertionError('Whole-image copy is too expensive per edited cell')
    s,item,exp,old=fixture()
    s.bin_data=NoBytes(bytes(2*1024*1024))
    s.bin_data[4]=9
    for i in range(200):
        assert decoded_table_cell(s,item,1,1,3)==3+10+100+9
    assert exp.bin_data is old
    assert exp.seen==[record for record in exp.seen]

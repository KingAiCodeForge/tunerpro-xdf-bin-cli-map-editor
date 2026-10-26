"""Exercise the offline runner with a fake *versioned* wheel and clean source.

This checks runner behaviour only, not genuine pinned parser correctness.
"""
import json
from pathlib import Path
import zipfile
import pytest
from run_offline_editor_qualification import hash_file, source_pin, wheel_identity, qualify


def setup(tmp_path):
    repo=tmp_path/'editor'; repo.mkdir()
    (repo/'pyproject.toml').write_text('[project]\ndependencies = ["kingai-tunerpro-xdf @ git+https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter.git@'+'a'*40+'"]\n')
    (repo/'cli_map_editor.py').write_text('VERSION=1\n')
    (repo/'test_probe.py').write_text('def test_probe(): assert 3 * 3 == 9\n')
    wheel=tmp_path/'kingai_tunerpro_xdf-3.7.5rc1-py3-none-any.whl'
    with zipfile.ZipFile(wheel,'w') as z:
        for item in ('tunerpro_exporter.py','tunerpro_xdf/__init__.py',
                     'tunerpro_xdf/xdf_equations.py', 'tunerpro_xdf/xdf_values.py'):
            z.writestr(item, '# only a runner fixture, not an Exporter\n')
        z.writestr('kingai_tunerpro_xdf-3.7.5rc1.dist-info/METADATA',
                   'Metadata-Version: 2.1\nName: kingai-tunerpro-xdf\nVersion: 3.7.5rc1\n')
    return repo,wheel


def test_runner_passes_selected_suite_offline_with_receipt(tmp_path):
    repo,wheel=setup(tmp_path)
    target=tmp_path/'receipts'
    assert qualify(repo,wheel,target,expected_sha256=hash_file(wheel),pytest_args=['test_probe.py']) == 0
    report=json.loads((target/'receipt.json').read_text())
    assert report['status']=='passed' and report['return_code']==0
    assert report['exporter_wheel']['sha256']==hash_file(wheel)
    assert report['pinned_exporter_commit']=='a'*40
    assert not report['native_tunerpro_parity_verified']
    assert not report['wheel_commit_provenance_verified']
    assert '1 passed' in (target/'pytest-output.txt').read_text()


def test_runner_records_failure_and_does_not_claim_success(tmp_path):
    repo,wheel=setup(tmp_path)
    (repo/'test_probe.py').write_text('def test_probe(): assert False\n')
    report_path=tmp_path/'reports'
    assert qualify(repo,wheel,report_path,pytest_args=['test_probe.py']) != 0
    report=json.loads((report_path/'receipt.json').read_text())
    assert report['status']=='failed' and report['return_code'] != 0


def test_wrong_hash_fails_without_creating_output(tmp_path):
    repo,wheel=setup(tmp_path)
    report_path=tmp_path/'reports'
    with pytest.raises(ValueError,match='wheel SHA-256 mismatch'):
        qualify(repo,wheel,report_path,expected_sha256='0'*64)
    assert not report_path.exists()


def test_runner_never_overwrites_existing_report_folder(tmp_path):
    repo,wheel=setup(tmp_path)
    out=tmp_path/'reports';out.mkdir();(out/'old.txt').write_text('preserve')
    with pytest.raises(FileExistsError):qualify(repo,wheel,out)
    assert (out/'old.txt').read_text()=='preserve'


@pytest.mark.parametrize('part', ['module','metadata','version'])
def test_invalid_wheel_is_rejected_before_execution(tmp_path, part):
    repo,wheel=setup(tmp_path)
    with zipfile.ZipFile(wheel,'w') as z:
        if part=='metadata': z.writestr('bad.dist-info/METADATA','Name: nope\n')
    if part=='module':
        new=tmp_path/'bad.whl'
        with zipfile.ZipFile(new,'w') as z:z.writestr('only.txt','x')
        wheel=new
    if part=='version':
        new=tmp_path/'incorrect.whl'
        with zipfile.ZipFile(new,'w') as z:
            for name in ('tunerpro_exporter.py','tunerpro_xdf/__init__.py','tunerpro_xdf/xdf_equations.py','tunerpro_xdf/xdf_values.py'):
                z.writestr(name,'')
            z.writestr('other.dist-info/METADATA','Name: kingai-tunerpro-xdf\nVersion: 1\n')
        wheel=new
    with pytest.raises(ValueError):wheel_identity(wheel)


def test_source_requires_exact_commit_pin(tmp_path):
    repo,wheel=setup(tmp_path)
    (repo/'pyproject.toml').write_text('[project]\nname="example"\n')
    with pytest.raises(ValueError,match='exact Exporter commit pin'):source_pin(repo)

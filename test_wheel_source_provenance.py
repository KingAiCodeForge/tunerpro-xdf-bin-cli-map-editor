"""Source-backed wheel provenance is stronger than a matching version label."""
from pathlib import Path
import json
import subprocess
import zipfile

import pytest
import run_offline_editor_qualification as qualification


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode().strip()


def fixture(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    git(source, 'init', '-q')
    (source / 'tunerpro_xdf').mkdir()
    payloads = {'tunerpro_exporter.py': b'# trusted\n',
                'tunerpro_xdf/__init__.py': b'# package\n'}
    for name, data in payloads.items():
        (source / name).write_bytes(data)
    git(source, 'add', '.')
    git(source, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-qm', 'Synthetic source only')
    pin = git(source, 'rev-parse', 'HEAD')
    wheel = tmp_path / 'fixture.whl'
    write_wheel(wheel, payloads)
    return source, wheel, pin, payloads


def write_wheel(path, payloads):
    with zipfile.ZipFile(path, 'w') as archive:
        for name, data in payloads.items():
            archive.writestr(name, data)


def test_exact_committed_python_payloads_are_proven(tmp_path):
    source, wheel, pin, _ = fixture(tmp_path)
    proof = qualification.verify_wheel_source(wheel, source, pin)
    assert proof['source_commit'] == pin
    assert proof['python_members_checked'] == 2
    assert proof['verified'] is True


def test_only_crlf_normalization_is_permitted(tmp_path):
    source, wheel, pin, payloads = fixture(tmp_path)
    write_wheel(wheel, {key: value.replace(b'\n', b'\r\n') for key, value in payloads.items()})
    assert qualification.verify_wheel_source(wheel, source, pin)['verified']


@pytest.mark.parametrize('kind', ['changed', 'extra', 'pth', 'traversal', 'noncanonical'])
def test_tampered_or_unowned_payloads_are_refused(tmp_path, kind):
    source, wheel, pin, payloads = fixture(tmp_path)
    if kind == 'changed':
        payloads['tunerpro_exporter.py'] = b'# replaced\n'
    elif kind == 'extra':
        payloads['untracked_payload.py'] = b'# not in Git\n'
    elif kind == 'pth':
        payloads['startup.pth'] = b'import injected\n'
    elif kind == 'traversal':
        payloads['../outside.py'] = b'# traversal\n'
    else:
        payloads['./tunerpro_exporter.py'] = payloads['tunerpro_exporter.py']
    write_wheel(wheel, payloads)
    with pytest.raises(ValueError):
        qualification.verify_wheel_source(wheel, source, pin)


def test_another_commit_cannot_be_claimed_by_version(tmp_path):
    source, wheel, pin, _ = fixture(tmp_path)
    with pytest.raises(ValueError, match='commit'):
        qualification.verify_wheel_source(wheel, source, '0' * 40)


def test_dirty_tracked_source_is_not_a_clean_build_pin(tmp_path):
    source, wheel, pin, _ = fixture(tmp_path)
    (source / 'tunerpro_exporter.py').write_bytes(b'# dirty\n')
    with pytest.raises(ValueError, match='dirty'):
        qualification.verify_wheel_source(wheel, source, pin)


def runner_fixture(tmp_path):
    source, wheel, _, payloads = fixture(tmp_path)
    for name in ('tunerpro_xdf/xdf_equations.py', 'tunerpro_xdf/xdf_values.py'):
        payloads[name] = b'# synthetic runner fixture, not a real parser\n'
        (source / name).write_bytes(payloads[name])
    git(source, 'add', '.')
    git(source, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        'commit', '-qm', 'Complete synthetic runner fixture')
    pin = git(source, 'rev-parse', 'HEAD')
    payloads['kingai_tunerpro_xdf-3.7.5rc1.dist-info/METADATA'] = (
        b'Metadata-Version: 2.1\nName: kingai-tunerpro-xdf\nVersion: 3.7.5rc1\n')
    write_wheel(wheel, payloads)
    editor = tmp_path / 'editor'
    editor.mkdir()
    (editor / 'pyproject.toml').write_text(
        '[project]\ndependencies=["kingai-tunerpro-xdf @ git+https://github.com/'
        'KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter.git@' + pin + '"]\n')
    (editor / 'cli_map_editor.py').write_text('# runner fixture only\n')
    (editor / 'test_probe.py').write_text('def test_probe(): assert 9 == 3 * 3\n')
    return source, wheel, pin, editor, payloads


def test_runner_records_verified_source_without_claiming_native_parity(tmp_path):
    source, wheel, pin, editor, _ = runner_fixture(tmp_path)
    report = tmp_path / 'report'
    assert qualification.qualify(editor, wheel, report, exporter_source=source,
                                 pytest_args=['test_probe.py']) == 0
    receipt = json.loads((report / 'receipt.json').read_text())
    assert receipt['wheel_commit_provenance_verified'] is True
    assert receipt['wheel_source_provenance']['source_commit'] == pin
    assert receipt['native_tunerpro_parity_verified'] is False
    assert receipt['real_ecu_image_validated'] is False


def test_runner_refuses_wrong_payload_before_creating_report(tmp_path):
    source, wheel, _, editor, payloads = runner_fixture(tmp_path)
    payloads['tunerpro_exporter.py'] = b'# substituted\n'
    write_wheel(wheel, payloads)
    report = tmp_path / 'report'
    with pytest.raises(ValueError, match='differs from source commit'):
        qualification.qualify(editor, wheel, report, exporter_source=source)
    assert not report.exists()

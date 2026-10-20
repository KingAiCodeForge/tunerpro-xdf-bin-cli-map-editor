"""Build and execute offline bundles using only generated tiny wheel fixtures."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

import build_portable_bundle as builder


COMMIT = 'a' * 40


def synthetic_wheel(root, name, version, dependencies=()):
    distribution = name.replace('-', '_')
    prefix = f'{distribution}-{version}.dist-info'
    entries = {
        f'{distribution}.py': b'SYNTHETIC_TEST_FIXTURE = True\n',
        f'{prefix}/METADATA': (
            f'Metadata-Version: 2.3\nName: {name}\nVersion: {version}\nRequires-Python: >=3.10\n'
            + ''.join(f'Requires-Dist: {requirement}\n' for requirement in dependencies) + '\n'
        ).encode('utf-8'),
        f'{prefix}/WHEEL': b'Wheel-Version: 1.0\nGenerator: synthetic-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    }
    record = io.StringIO(newline='')
    writer = csv.writer(record)
    for filename, data in entries.items():
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode('ascii')
        writer.writerow([filename, f'sha256={digest}', len(data)])
    writer.writerow([f'{prefix}/RECORD', '', ''])
    entries[f'{prefix}/RECORD'] = record.getvalue().encode('utf-8')
    path = root / f'{distribution}-{version}-py3-none-any.whl'
    with zipfile.ZipFile(path, 'w') as wheel:
        for filename, data in entries.items():
            wheel.writestr(filename, data)
    return path


def make_bundle(tmp_path):
    source = tmp_path / 'wheel sources with spaces'
    source.mkdir()
    requirement = f'kingai-tunerpro-xdf @ {builder.EXPORTER_URL}{COMMIT}'
    editor = synthetic_wheel(source, 'kingai-tunerpro-map-editor', '1.2.0rc1', [requirement])
    exporter = synthetic_wheel(source, 'kingai-tunerpro-xdf', '3.7.5rc1')
    output = tmp_path / 'portable bundle.zip'
    builder.build_bundle(editor, exporter, COMMIT, output)
    return output, editor, exporter


def extract_bundle(output, destination, *, omit=None):
    destination.mkdir()
    with zipfile.ZipFile(output) as archive:
        for member in archive.namelist():
            if member != omit:
                archive.extract(member, destination)


def run_installer(root, caller, *args):
    return subprocess.run([sys.executable, '-I', str(root / 'install.py'), *map(str, args)],
                          cwd=caller, capture_output=True, text=True, encoding='utf-8', timeout=120)


def test_bundle_is_reproducible_and_exclusive(tmp_path):
    output, editor, exporter = make_bundle(tmp_path)
    original = output.read_bytes()
    second = tmp_path / 'second.zip'
    builder.build_bundle(editor, exporter, COMMIT, second)
    assert second.read_bytes() == original
    with pytest.raises(FileExistsError):
        builder.build_bundle(editor, exporter, COMMIT, output)
    assert output.read_bytes() == original
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read('portable-manifest.json'))
        assert manifest['exporter_commit'] == COMMIT
        assert len(manifest['wheels']) == 2
        for line in archive.read('SHA256SUMS.txt').decode('ascii').splitlines():
            digest, name = line.split('  ', 1)
            assert hashlib.sha256(archive.read(name)).hexdigest() == digest


def test_bundle_rejects_different_dependency_commit(tmp_path):
    _output, editor, exporter = make_bundle(tmp_path)
    refused = tmp_path / 'must not publish.zip'
    with pytest.raises(ValueError, match='dependency does not match'):
        builder.build_bundle(editor, exporter, 'b' * 40, refused)
    assert not refused.exists()


@pytest.mark.parametrize('damage', ['missing', 'corrupted'])
def test_installer_checks_wheels_before_creating_environment(tmp_path, damage):
    output, editor, _exporter = make_bundle(tmp_path)
    root = tmp_path / 'extracted bundle with spaces'
    omitted = f'wheels/{editor.name}' if damage == 'missing' else None
    extract_bundle(output, root, omit=omitted)
    if damage == 'corrupted':
        (root / 'wheels' / editor.name).write_bytes(b'corrupted synthetic wheel')
    result = run_installer(root, tmp_path)
    assert result.returncode != 0
    assert 'ERROR' in result.stderr
    assert not (root / '.venv').exists()


def test_installer_refuses_existing_environment_without_changes(tmp_path):
    output, _editor, _exporter = make_bundle(tmp_path)
    root = tmp_path / 'existing installation bundle'
    extract_bundle(output, root)
    destination = root / '.venv'
    destination.mkdir()
    marker = destination / 'keep.txt'
    marker.write_text('preserved', encoding='utf-8')
    result = run_installer(root, tmp_path)
    assert result.returncode != 0
    assert 'Refusing existing environment' in result.stderr
    assert list(destination.iterdir()) == [marker]
    assert marker.read_text(encoding='utf-8') == 'preserved'


def test_offline_bundle_installs_into_new_environment_with_spaces(tmp_path):
    output, _editor, _exporter = make_bundle(tmp_path)
    root = tmp_path / 'offline package with spaces'
    extract_bundle(output, root)
    target = tmp_path / 'new isolated environment with spaces'
    result = run_installer(root, tmp_path, '--venv', target)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Offline installation verified' in result.stdout
    python = target / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    checked = subprocess.run(
        [str(python), '-I', '-c',
         'from importlib.metadata import version; print(version("kingai-tunerpro-map-editor")); print(version("kingai-tunerpro-xdf"))'],
        capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert checked.returncode == 0, checked.stderr
    assert checked.stdout.splitlines() == ['1.2.0rc1', '3.7.5rc1']

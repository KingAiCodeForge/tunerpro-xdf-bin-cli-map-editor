"""Execute real CLI processes with synthetic inputs outside the checkout."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import cli_map_editor as editor


def run_cli(cwd, *args):
    return subprocess.run(
        [sys.executable, str(Path(editor.__file__).resolve()), *map(str, args)],
        cwd=cwd, capture_output=True, text=True, encoding='utf-8', timeout=30,
    )


def test_cli_in_unrelated_directory_with_spaces_preserves_inputs(tmp_path):
    cwd = tmp_path / 'unrelated caller directory'
    cwd.mkdir()
    xdf = cwd / 'synthetic definition.xdf'
    binary = cwd / 'synthetic original.bin'
    xdf.write_text(
        '<XDFFORMAT><XDFHEADER><deftitle>Synthetic portability</deftitle></XDFHEADER>'
        '<XDFCONSTANT uniqueid="1"><title>Scalar</title>'
        '<EMBEDDEDDATA mmedaddress="0" mmedelementsizebits="8"/>'
        '<MATH equation="X"/></XDFCONSTANT>'
        '<XDFTABLE uniqueid="2"><title>Table</title><XDFAXIS id="z">'
        '<EMBEDDEDDATA mmedaddress="2" mmedelementsizebits="8" '
        'mmedrowcount="1" mmedcolcount="2"/><MATH equation="X"/>'
        '</XDFAXIS></XDFTABLE>'
        '<XDFFLAG><title>Flag</title><EMBEDDEDDATA mmedaddress="8"/>'
        '<mask>1</mask></XDFFLAG></XDFFORMAT>', encoding='utf-8',
    )
    original = bytes([5, 0, 7, 9, 0, 0, 0, 0, 0xA4]) + bytes(55)
    binary.write_bytes(original)
    xdf_bytes = xdf.read_bytes()
    common = ['--xdf', xdf, '--bin', binary]
    preflight = run_cli(cwd, 'preflight', *common)
    assert preflight.returncode == 0, preflight.stdout + preflight.stderr

    operations = [
        ('edit-scalar', ['--name', 'Scalar', '--value', '11'], 0, 11),
        ('edit', ['--map', 'Table', '--rows', '1', '--cols', '2', '--value', '13'], 3, 13),
        ('edit-flag', ['--name', 'Flag', '--state', 'set'], 8, 0xA5),
    ]
    for command, specific, offset, value in operations:
        destination = cwd / f'{command} reviewed outputs'
        result = run_cli(cwd, command, *common, *specific, '--autosave', '--output-dir', destination)
        assert result.returncode == 0, result.stdout + result.stderr
        outputs = list(destination.glob('*.bin'))
        assert len(outputs) == 1
        expected = bytearray(original)
        expected[offset] = value
        assert outputs[0].read_bytes() == expected
        assert len(list(destination.glob('*.log'))) == 1
        assert len(list(destination.glob('*_detailed.csv'))) == 1
        diff = run_cli(cwd, 'diff', '--bin-a', binary, '--bin-b', outputs[0], '--xdf', xdf)
        assert diff.returncode == 0, diff.stdout + diff.stderr

    fixture = cwd / 'exact pair fixture.json'
    fixture.write_text(json.dumps({
        'schema': 'kingai.exact-bin-xdf-fixture.v1', 'target_id': 'synthetic',
        'bin': {'size': len(original), 'sha256': hashlib.sha256(original).hexdigest()},
        'xdf': {'sha256': hashlib.sha256(xdf_bytes).hexdigest()},
    }), encoding='utf-8')
    validation = run_cli(cwd, 'validate-fixture', *common, '--fixture', fixture, '--target-id', 'synthetic')
    assert validation.returncode == 0, validation.stdout + validation.stderr
    snapshots = cwd / 'reviewed snapshot outputs'
    exported = run_cli(cwd, 'export-fixture', *common, '--fixture', fixture,
                       '--target-id', 'synthetic', '--output-dir', snapshots)
    assert exported.returncode == 0, exported.stdout + exported.stderr
    copies = list(snapshots.rglob('*.bin'))
    assert len(copies) == 1
    assert copies[0].read_bytes() == original
    denied_output = cwd / 'must not export mismatch'
    wrong_fixture = json.loads(fixture.read_text(encoding='utf-8'))
    wrong_fixture['bin']['sha256'] = '0' * 64
    fixture.write_text(json.dumps(wrong_fixture), encoding='utf-8')
    refused = run_cli(cwd, 'export-fixture', *common, '--fixture', fixture,
                      '--target-id', 'synthetic', '--output-dir', denied_output)
    assert refused.returncode != 0
    assert 'BIN SHA-256 mismatch' in refused.stdout
    assert not denied_output.exists()
    assert binary.read_bytes() == original
    assert xdf.read_bytes() == xdf_bytes


def test_missing_inputs_return_errors_without_output(tmp_path):
    for command in ('preflight', 'export'):
        args = ['--xdf', 'missing definition.xdf', '--bin', 'missing image.bin']
        if command == 'export':
            args += ['--output-dir', 'must not create']
        result = run_cli(tmp_path, command, *args)
        assert result.returncode != 0
        assert 'ERROR' in result.stdout or 'FAIL' in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_missing_exporter_reports_install_instruction(tmp_path):
    import tunerpro_exporter_for_cli_editor_version as wrapper
    standalone = tmp_path / 'dependency wrapper.py'
    standalone.write_bytes(Path(wrapper.__file__).read_bytes())
    result = subprocess.run(
        [sys.executable, '-I', '-S', str(standalone)], cwd=tmp_path,
        capture_output=True, text=True, encoding='utf-8', timeout=30,
    )
    assert result.returncode != 0
    assert 'Install the editor and its pinned shared XDF dependency' in result.stderr
    assert 'python -m pip install .' in result.stderr

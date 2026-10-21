#!/usr/bin/env python3
"""Execute Editor pytest locally against an independently supplied Exporter wheel.

No GitHub Actions, network, pip install, firmware, flasher, or ECU hardware.
An Exporter wheel is executable Python: only supply one from a trusted source.
The result is synthetics-only until native exact-pair replay is independently done.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile
from email.parser import Parser

PIN_RE = re.compile(r'KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter\.git@([a-f0-9]{40})')
REQUIRED = {'tunerpro_exporter.py', 'tunerpro_xdf/__init__.py',
            'tunerpro_xdf/xdf_equations.py', 'tunerpro_xdf/xdf_values.py'}


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def wheel_identity(path: Path) -> dict:
    """Reject malformed or unexpected wheels before executing arbitrary code."""
    if not path.is_file() or path.suffix.lower() != '.whl':
        raise ValueError('Expected an existing local .whl file')
    with zipfile.ZipFile(path) as z:
        entries = z.namelist()
        if len(entries) != len(set(entries)):
            raise ValueError('Wheel contains duplicate archive paths')
        if not REQUIRED <= set(entries):
            raise ValueError('Wheel is missing required XDF parser modules')
        metadata_paths = [x for x in entries if x.endswith('.dist-info/METADATA')]
        if len(metadata_paths) != 1:
            raise ValueError('Wheel must include exactly one METADATA file')
        record = Parser().parsestr(z.read(metadata_paths[0]).decode('utf-8'))
        name = record.get('Name', '').lower().replace('_', '-')
        version = record.get('Version', '')
        if (name, version) != ('kingai-tunerpro-xdf', '3.7.5rc1'):
            raise ValueError(f'Unexpected Exporter wheel {name} {version}')
    return {'name': name, 'version': version, 'sha256': hash_file(path),
            'filename': path.name}


def source_pin(repo: Path) -> str:
    pyproject = repo / 'pyproject.toml'
    if not pyproject.is_file():
        raise ValueError('Editor source directory requires pyproject.toml')
    match = PIN_RE.search(pyproject.read_text(encoding='utf-8'))
    if not match:
        raise ValueError('Editor source does not declare an exact Exporter commit pin')
    if not (repo / 'cli_map_editor.py').is_file():
        raise ValueError('Missing CLI source module')
    return match.group(1)


def qualify(repo: Path, wheel: Path, report_dir: Path,
            expected_sha256: str | None = None, pytest_args: list[str] | None = None) -> int:
    repo = repo.resolve(strict=True)
    wheel = wheel.resolve(strict=True)
    pin = source_pin(repo)
    identity = wheel_identity(wheel)
    if expected_sha256 is not None:
        expected = expected_sha256.strip().lower()
        if len(expected) != 64 or any(x not in '0123456789abcdef' for x in expected):
            raise ValueError('Expected wheel SHA-256 requires 64 hex characters')
        if expected != identity['sha256']:
            raise ValueError('Exporter wheel SHA-256 mismatch')
    if report_dir.resolve() == repo or report_dir.resolve() == wheel.parent:
        raise ValueError('Report directory must be a new, separate folder')
    report_dir.mkdir(parents=True, exist_ok=False)
    stdout = report_dir / 'pytest-output.txt'
    receipt = report_dir / 'receipt.json'
    command = [sys.executable, '-m', 'pytest', '-q']
    command += list(pytest_args or [])
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([str(repo), str(wheel)])
    status = 'failed'
    code = -1
    try:
        with stdout.open('x', encoding='utf-8') as output:
            output.write('Command: ' + repr(command) + '\n')
            output.write('Local Exporter wheel: ' + identity['filename'] + '\n')
            output.write('Pinned source commit: ' + pin + '\n\n')
            output.flush()
            completed = subprocess.run(command, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=subprocess.STDOUT, check=False)
            code = completed.returncode
            status = 'passed' if code == 0 else 'failed'
    finally:
        receipt.write_text(json.dumps({
            'schema': 'kingai.editor-offline-qualification.v1',
            'status': status, 'return_code': code,
            'python': sys.version.split()[0], 'editor_source': str(repo),
            'pinned_exporter_commit': pin, 'exporter_wheel': identity,
            'evidence': 'pytest-output.txt',
            'native_tunerpro_parity_verified': False,
            'real_ecu_image_validated': False,
            'wheel_commit_provenance_verified': False,
        }, indent=2) + '\n', encoding='utf-8')
    return code


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path.cwd(), help='Existing Editor source checkout')
    p.add_argument('--exporter-wheel', required=True, type=Path, help='Trusted exact-version local wheel')
    p.add_argument('--report-dir', required=True, type=Path, help='New, private report directory')
    p.add_argument('--expected-wheel-sha256', help='Optional independently established SHA-256')
    p.add_argument('pytest_args', nargs=argparse.REMAINDER, help='Arguments after -- passed to pytest')
    args = p.parse_args(argv)
    extras = args.pytest_args
    if extras and extras[0] == '--':
        extras = extras[1:]
    try:
        return qualify(args.repo, args.exporter_wheel, args.report_dir,
                       args.expected_wheel_sha256, extras)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

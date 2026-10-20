"""Build an offline Python bundle from exactly selected Editor/Exporter wheels."""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile

import portable_install


EXPORTER_URL = 'git+https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter.git@'


def _read_wheel(path: Path, expected_name: str) -> tuple[bytes, dict, list[str]]:
    if not re.fullmatch(r'[A-Za-z0-9_.+-]+\.whl', path.name):
        raise ValueError(f'Invalid wheel filename: {path.name}')
    data = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as wheel:
        metadata_paths = [name for name in wheel.namelist() if name.endswith('.dist-info/METADATA')]
        if len(metadata_paths) != 1:
            raise ValueError(f'Expected exactly one wheel metadata record: {path.name}')
        metadata = BytesParser().parsebytes(wheel.read(metadata_paths[0]))
    name = re.sub(r'[-_.]+', '-', str(metadata.get('Name', ''))).lower()
    if name != expected_name:
        raise ValueError(f'Wrong wheel package: expected {expected_name}, got {name}')
    if str(metadata.get('License-Expression') or metadata.get('License') or '').strip() != 'MIT':
        raise ValueError(f'Wheel must declare the reviewed MIT licence: {path.name}')
    version = str(metadata.get('Version', ''))
    if not version:
        raise ValueError(f'Wheel has no version: {path.name}')
    expected_filename = f'{expected_name.replace("-", "_")}-{version}-py3-none-any.whl'
    if path.name != expected_filename:
        raise ValueError(f'Only portable pure-Python wheels are supported: {path.name}')
    entry = {'name': name, 'version': version, 'filename': path.name,
             'sha256': hashlib.sha256(data).hexdigest()}
    return data, entry, metadata.get_all('Requires-Dist', [])


def build_bundle(editor_wheel: Path, exporter_wheel: Path, exporter_commit: str, output: Path) -> Path:
    if not re.fullmatch(r'[0-9a-f]{40}', exporter_commit):
        raise ValueError('Exporter commit must be an exact lowercase 40-character Git SHA')
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Refusing existing bundle: {output}')
    editor_data, editor_entry, requirements = _read_wheel(editor_wheel, 'kingai-tunerpro-map-editor')
    exporter_data, exporter_entry, _ = _read_wheel(exporter_wheel, 'kingai-tunerpro-xdf')
    expected_pin = f'kingai-tunerpro-xdf @ {EXPORTER_URL}{exporter_commit}'
    if expected_pin not in requirements:
        raise ValueError('Editor wheel dependency does not match the exact supplied Exporter commit')
    installer = Path(portable_install.__file__).read_bytes()
    manifest = {'schema': portable_install.SCHEMA, 'python_requires': '>=3.10',
                'exporter_commit': exporter_commit, 'wheels': [editor_entry, exporter_entry],
                'installer_sha256': hashlib.sha256(installer).hexdigest()}
    readme = (
        f'KingAI Editor {editor_entry["version"]} / Exporter {exporter_entry["version"]}\n'
        'Offline portable Python bundle — requires Python 3.10+ with venv/ensurepip.\n\n'
        'Extract into a new folder. From any working directory, run:\n'
        '  python "path to extracted bundle/install.py"\n'
        'The installer verifies its own and both wheel SHA-256 values before creating a new\n'
        'environment. It installs local wheels with no index and no dependencies,\n'
        'then runs pip check. An existing .venv is refused and never overwritten.\n'
        'Use --venv "new environment path" to select another new directory.\n'
        'Failed installations are retained for inspection; choose a fresh path.\n\n'
        'After installation run the printed Python command with --help.\n'
        'This bundle includes no Python interpreter or standalone executable,\n'
        'firmware, XDF definition, customer data, or local configuration.\n'
        'Both wheels declare MIT licence metadata. Check the release evidence\n'
        'for tested platforms, skipped corpus, and native-parity limitations.\n'
        'This is experimental offline inspection/editing software; it does not\n'
        'qualify an ECU definition, tune, checksum repair or flashing operation.\n\n'
        f'Editor dependency declares Exporter source commit: {exporter_commit}\n'
        'Checksums detect corruption; they are not a publisher signature.\n'
    ).encode('utf-8')
    members = {'install.py': installer, 'README.txt': readme,
               'portable-manifest.json': (json.dumps(manifest, indent=2) + '\n').encode('utf-8'),
               f'wheels/{editor_wheel.name}': editor_data, f'wheels/{exporter_wheel.name}': exporter_data}
    checksums = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data in sorted(members.items()))
    members['SHA256SUMS.txt'] = checksums.encode('ascii')
    # All inputs have been read and checked. Exclusive creation protects old assets.
    with output.open('xb') as handle, zipfile.ZipFile(handle, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor-wheel', type=Path, required=True)
    parser.add_argument('--exporter-wheel', type=Path, required=True)
    parser.add_argument('--exporter-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_bundle(args.editor_wheel, args.exporter_wheel, args.exporter_commit, args.output)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    print(f'Created {result.name}: SHA256 {hashlib.sha256(result.read_bytes()).hexdigest()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

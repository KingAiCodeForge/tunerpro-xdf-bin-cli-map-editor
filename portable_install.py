"""Install a checksum-verified offline Editor/Exporter bundle into a new venv."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import venv


SCHEMA = 'kingai.editor-offline-bundle.v1'


def verify_bundle(root: Path) -> list[Path]:
    """Validate every selected wheel before creating an installation directory."""
    root = root.resolve()
    manifest = json.loads((root / 'portable-manifest.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA:
        raise ValueError('Unsupported portable bundle manifest')
    installer_digest = manifest.get('installer_sha256')
    if not isinstance(installer_digest, str) or not re.fullmatch(r'[0-9a-f]{64}', installer_digest):
        raise ValueError('Invalid installer SHA-256')
    if hashlib.sha256((root / 'install.py').read_bytes()).hexdigest() != installer_digest:
        raise ValueError('Installer checksum mismatch')
    if manifest.get('python_requires') != '>=3.10' or not re.fullmatch(
            r'[0-9a-f]{40}', str(manifest.get('exporter_commit', ''))):
        raise ValueError('Invalid Python requirement or Exporter commit in manifest')
    wheels = manifest.get('wheels')
    if not isinstance(wheels, list) or len(wheels) != 2:
        raise ValueError('Bundle must declare exactly the Editor and Exporter wheels')
    expected_names = {'kingai-tunerpro-map-editor', 'kingai-tunerpro-xdf'}
    declared_names = set()
    verified = []
    for entry in wheels:
        if not isinstance(entry, dict):
            raise ValueError('Invalid wheel manifest entry')
        name, filename, digest = entry.get('name'), entry.get('filename'), entry.get('sha256')
        if not isinstance(name, str) or name not in expected_names or name in declared_names:
            raise ValueError('Unexpected or duplicate wheel package')
        if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9_.+-]+\.whl', filename):
            raise ValueError('Invalid wheel filename')
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Invalid wheel SHA-256')
        path = root / 'wheels' / filename
        if path.is_symlink() or path.resolve().parent != root / 'wheels':
            raise ValueError('Wheel path must stay inside the bundle wheels directory')
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise ValueError(f'Wheel checksum mismatch: {filename}')
        declared_names.add(name)
        verified.append(path)
    if declared_names != expected_names:
        raise ValueError('Missing Editor or Exporter package')
    return verified


def install_bundle(root: Path, destination: Path) -> Path:
    """Create only a new venv, preserve failed installations for inspection."""
    if sys.version_info < (3, 10):
        raise ValueError('Python 3.10 or later is required')
    if os.path.lexists(destination):
        raise FileExistsError(f'Refusing existing environment: {destination}')
    wheels = verify_bundle(root)
    # Reserve exclusively after all integrity checks. Never reuse a caller's venv.
    destination.mkdir()
    try:
        try:
            venv.EnvBuilder(with_pip=True).create(destination)
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                f'Python venv/ensurepip support is required. Incomplete environment retained at {destination}: {exc}'
            ) from exc
        python = destination / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        # --isolated alone still reads global/site pip config, which could redirect
        # writes via target/prefix. os.devnull disables every pip config file.
        child_env = dict(os.environ, PIP_CONFIG_FILE=os.devnull)
        subprocess.run(
            [str(python), '-I', '-m', 'pip', '--isolated', 'install',
             '--no-index', '--no-deps', '--disable-pip-version-check', *map(str, wheels)],
            check=True, timeout=120, env=child_env,
        )
        subprocess.run([str(python), '-I', '-m', 'pip', '--isolated', 'check'],
                       check=True, timeout=120, env=child_env)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f'Installation incomplete; retained for inspection at {destination}: {exc}') from exc
    return python


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--venv', type=Path, help='New environment path; existing paths are refused')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    destination = args.venv or root / '.venv'
    try:
        python = install_bundle(root, destination.absolute())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    print(f'Offline installation verified. Run: "{python}" -m cli_map_editor --help')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

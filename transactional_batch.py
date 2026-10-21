"""Atomic *in-memory* multi-item XDF edits for KingAI's CLI map editor.

The owner-approved plan is staged against one exact XDF/BIN pair. Each value is
written by the existing typed editor; the entire result is validated before
publishing a new BIN through the existing audited save routine. This module
has no dependency on the ECU parser and is deliberately easy to unit test.
"""

from __future__ import annotations

import csv
import hashlib
import math
from pathlib import Path
from typing import Any


ALLOWED_COLUMNS = {'type', 'map', 'row', 'col', 'value', 'raw'}
KINDS = {'table', 'scalar', 'flag'}


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def _require_hash(label: str, observed: str, expected: str | None) -> None:
    if expected is None:
        return
    expected = expected.strip().lower()
    if len(expected) != 64 or any(char not in '0123456789abcdef' for char in expected):
        raise ValueError(f'{label} expected SHA-256 must contain exactly 64 hex digits')
    if observed != expected:
        raise ValueError(f'{label} SHA-256 does not match --expected-{label.lower()}-sha256: '
                         f'expected={expected}, actual={observed}')


def read_plan(csv_path: str, default_map: str | None = None) -> list[dict[str, Any]]:
    """Parse all operations before loading a mutable session. Blank lines are ignored."""
    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames is None:
            raise ValueError('Edit CSV is empty or missing its header')
        names = [name.strip().lower() for name in reader.fieldnames if name is not None]
        if len(names) != len(reader.fieldnames) or len(names) != len(set(names)):
            raise ValueError('Edit CSV contains duplicate or blank headers')
        if not {'value'} <= set(names):
            raise ValueError('Edit CSV requires a value column')
        unknown = set(names) - ALLOWED_COLUMNS
        if unknown:
            raise ValueError(f'Unrecognized edit CSV columns: {sorted(unknown)}')
        reader.fieldnames = names
        result = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f'CSV row {row_number} contains excess columns')
            if not any((value or '').strip() for value in row.values()):
                continue
            kind = (row.get('type') or 'table').strip().lower()
            if kind not in KINDS:
                raise ValueError(f'CSV row {row_number}: unsupported type {kind!r}')
            name = (row.get('map') or default_map or '').strip()
            if not name:
                raise ValueError(f'CSV row {row_number}: map must be an exact XDF title')
            target = (row.get('value') or '').strip()
            if not target:
                raise ValueError(f'CSV row {row_number}: value must not be blank')
            raw_text = (row.get('raw') or '').strip().lower()
            if raw_text not in ('', '0', '1', 'false', 'true', 'no', 'yes'):
                raise ValueError(f'CSV row {row_number}: raw must be 0/1 or true/false')
            raw = raw_text in ('1', 'true', 'yes')
            r, c = (row.get('row') or '').strip(), (row.get('col') or '').strip()
            if kind == 'table':
                if not r or not c:
                    raise ValueError(f'CSV row {row_number}: table requires row and col')
            elif r or c:
                raise ValueError(f'CSV row {row_number}: {kind} must not specify row/col')
            if kind == 'flag':
                if raw:
                    raise ValueError(f'CSV row {row_number}: raw is not meaningful for flags')
                value: float | str = target
            else:
                try:
                    value = float(target)
                except ValueError as exc:
                    raise ValueError(f'CSV row {row_number}: invalid numeric value {target!r}') from exc
                if not math.isfinite(value):
                    raise ValueError(f'CSV row {row_number}: value must be finite')
                if raw and not value.is_integer():
                    raise ValueError(f'CSV row {row_number}: raw value must be an integer')
            result.append({'line': row_number, 'type': kind, 'name': name,
                           'row': r, 'col': c, 'value': value, 'raw': raw})
    if not result:
        raise ValueError('Edit CSV contains no operations')
    return result


def _view_value(session, kind, item, row=0, col=0, raw=None):
    """Re-evaluate a single cell at full precision without decoding a whole map."""
    if kind == 'table':
        z = item['axes']['z']
        variables = session._current_variables(z, item, row - 1, col - 1)
        result, _ = session.exporter.evaluate_math(z.get('equation', ''), raw,
                                                  linked_vars=variables)
        if result is None:
            raise ValueError(f"Cannot re-evaluate table {item['title']!r}")
        return result
    if kind == 'scalar':
        return session.read_scalar_value(item)[1]
    return session.read_flag_state(item)[1]


def _claim_bytes(change: dict, item: dict, claims: dict[int, tuple[int, str]]):
    """Block aliasing writes; two different flags may touch disjoint bit masks."""
    offset = int(change['file_offset'], 16)
    bits = change['size_bits']
    if type(bits) is not int or bits <= 0 or bits % 8:
        raise ValueError(f"Invalid written storage width {bits!r}")
    byte_masks = [0xFF] * (bits // 8)
    if change['type'] == 'flag':
        mask = item.get('mask', 0x01)
        if type(mask) is not int or not 0 < mask <= 0xFF or bits != 8:
            raise ValueError('Flag requires an explicit 8-bit mask')
        byte_masks = [mask]
    for i, mask in enumerate(byte_masks):
        earlier = claims.get(offset + i)
        if earlier and earlier[0] & mask:
            raise ValueError(f"Conflicting XDF writes at file offset 0x{offset + i:X}: "
                             f"{earlier[1]!r} and {change['map']!r}")
    for i, mask in enumerate(byte_masks):
        before_mask, before_name = claims.get(offset + i, (0, ''))
        claims[offset + i] = (before_mask | mask, before_name or change['map'])


def _stage_item(session, op: dict, parse_range, parse_flag_state,
                claims: dict, expectations: list, touched_tables: set):
    kind, name = op['type'], op['name']
    if kind == 'table':
        item = session.find_table(name)
        if item is None:
            raise ValueError(f"CSV row {op['line']}: table {name!r} not found")
        rows, cols = session.get_table_dimensions(item)
        row_range, col_range = parse_range(op['row']), parse_range(op['col'])
        # Validate endpoints before expansion, so a typo cannot generate a huge loop.
        if (not row_range or not col_range or row_range.start < 1 or col_range.start < 1
                or row_range.stop - 1 > rows or col_range.stop - 1 > cols):
            raise ValueError(f"CSV row {op['line']}: cell selection outside {rows}x{cols} table")
        for row in row_range:
            for col in col_range:
                change = session.write_table_cell(item, row, col, op['value'], raw_mode=op['raw'])
                _claim_bytes(change, item, claims)
                expectations.append((kind, item, row, col, change,
                                     _view_value(session, kind, item, row, col, change['new_raw'])))
        if id(item) not in touched_tables:
            session.add_table_log_entry(item['title'])
            touched_tables.add(id(item))
    elif kind == 'scalar':
        item = session.find_constant(name)
        if item is None:
            raise ValueError(f"CSV row {op['line']}: scalar {name!r} not found")
        change = session.write_scalar(item, op['value'], raw_mode=op['raw'])
        _claim_bytes(change, item, claims)
        expectations.append((kind, item, 0, 0, change,
                             _view_value(session, kind, item)))
    else:
        item = session.find_flag(name)
        if item is None:
            raise ValueError(f"CSV row {op['line']}: flag {name!r} not found")
        state = parse_flag_state(op['value'])
        change = session.write_flag(item, state)
        _claim_bytes(change, item, claims)
        expectations.append((kind, item, 0, 0, change,
                             _view_value(session, kind, item)))


def _verify_final(session, before: bytes, claims: dict, expectations: list) -> list[int]:
    after = bytes(session.bin_data)
    if len(before) != len(after):
        raise ValueError('Edit changed the BIN length')
    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    for offset in changed:
        permitted = claims.get(offset)
        if permitted is None:
            raise ValueError('Edit changed a byte not claimed by an XDF operation')
        if (before[offset] ^ after[offset]) & ~permitted[0]:
            raise ValueError(f'Edit changed undeclared bit(s) at file offset 0x{offset:X}')
    for kind, item, row, col, change, view in expectations:
        offset = int(change['file_offset'], 16)
        if kind == 'flag':
            actual = session.read_flag_state(item)[1]
            if actual != view:
                raise ValueError(f"Final flag state changed for {item['title']!r}")
            continue
        size = change['size_bits']
        storage = item['axes']['z'] if kind == 'table' else item
        actual_raw = session._read_raw_at(offset, size, storage.get('signed', False),
                                          storage.get('lsb_first', False))
        if actual_raw != change['new_raw']:
            raise ValueError(f"Final raw value changed for {item['title']!r}")
        observed = _view_value(session, kind, item, row, col, actual_raw)
        if observed != view:
            raise ValueError(f"Final-image XDF conversion dependency changed for {item['title']!r} "
                             f"at [{row},{col}]: expected={view!r}, actual={observed!r}")
    return changed


def run_batch(args, session_factory, parse_range, parse_flag_state) -> int:
    """Stage, validate and optionally save a typed CSV of XDF edits.

    Without --autosave this performs a dry run. --autosave requires --output-dir
    and uses the existing exclusive, audited three-file publication routine.
    """
    autosave = bool(getattr(args, 'autosave', False))
    output_dir = getattr(args, 'output_dir', None)
    if autosave and not output_dir:
        raise ValueError('Batch publication requires --autosave --output-dir')
    if not autosave and output_dir:
        raise ValueError('An output directory without --autosave is ambiguous; remove it for preview')
    plan = read_plan(args.csv, getattr(args, 'default_map', None))
    bin_hash = _sha256(args.bin)
    xdf_hash = _sha256(args.xdf)
    _require_hash('BIN', bin_hash, getattr(args, 'expected_bin_sha256', None))
    _require_hash('XDF', xdf_hash, getattr(args, 'expected_xdf_sha256', None))
    session = session_factory(args.xdf, args.bin)
    if not session.load():
        raise ValueError('Cannot load exact XDF/BIN pair')
    before = bytes(session.bin_data)
    if hashlib.sha256(before).hexdigest() != bin_hash:
        raise ValueError('BIN changed while loading; identity check failed')
    if _sha256(args.xdf) != xdf_hash:
        raise ValueError('XDF changed while loading; identity check failed')
    counts = (len(session.changes), len(session.log_entries))
    claims: dict[int, tuple[int, str]] = {}
    expectations = []
    touched_tables = set()
    try:
        for operation in plan:
            _stage_item(session, operation, parse_range, parse_flag_state,
                        claims, expectations, touched_tables)
        changed = _verify_final(session, before, claims, expectations)
    except BaseException:
        session.bin_data[:] = before
        del session.changes[counts[0]:]
        del session.log_entries[counts[1]:]
        raise
    after = bytes(session.bin_data)
    after_hash = hashlib.sha256(after).hexdigest()
    print(f'XDF SHA-256: {xdf_hash}')
    print(f'BIN SHA-256: {bin_hash}')
    print(f'Operations: {len(plan)} CSV rows; {len(expectations)} typed targets; '
          f'{len(changed)} changed bytes (of {len(before)})')
    print(f'Proposed BIN SHA-256: {after_hash}')
    for change in session.changes[:60]:
        location = (f"[{change['row']},{change['col']}]" if change['type'] == 'table' else '')
        print(f"  {change['type']} {change['map']}{location}: "
              f"{change['old_real']} -> {change['new_real']} {change.get('unit', '')} "
              f"raw {change['old_raw']} -> {change['new_raw']} "
              f"file {change['file_offset']}")
    if len(session.changes) > 60:
        print(f'  ... {len(session.changes) - 60} additional typed changes in audit CSV')
    if autosave:
        if _sha256(args.bin) != bin_hash or _sha256(args.xdf) != xdf_hash:
            raise ValueError('Source BIN/XDF changed while staging; refusing to save')
        bin_out, log_out = session.save_final(output_dir, 'batch')
        published = Path(bin_out).read_bytes()
        if published != after:
            raise ValueError('Published BIN differs from the validated staged image; treat save as invalid')
        print(f'Saved new BIN: {bin_out}')
        print(f'Audit log: {log_out}')
        print('The saved image has not been checksum-repaired, flashed, or vehicle-validated.')
    else:
        print('DRY RUN: no BIN or audit files written; use --autosave --output-dir to publish.')
    return 0

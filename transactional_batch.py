"""Atomic *in-memory* multi-item XDF edits for KingAI's CLI map editor.

The owner-approved plan is staged against one exact XDF/BIN pair. Each value is
written by the existing typed editor; the entire result is validated before
publishing a new BIN through the existing audited save routine. This module
has no dependency on the ECU parser and is deliberately easy to unit test.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from batch_plan_snapshot import snapshot_plan


ALLOWED_COLUMNS = {'type', 'map', 'row', 'col', 'value', 'raw', 'expected_raw', 'uniqueid', 'address', 'flag_mask'}
KINDS = {'table', 'scalar', 'flag'}
CSV_COLUMNS = ('type', 'map', 'row', 'col', 'value', 'raw', 'expected_raw', 'uniqueid', 'address', 'flag_mask')


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


def read_plan(csv_path, default_map: str | None = None) -> list[dict[str, Any]]:
    """Parse all operations before loading a mutable session. Blank lines are ignored."""
    source = (open(csv_path, 'r', encoding='utf-8-sig', newline='')
              if isinstance(csv_path, (str, Path)) else nullcontext(csv_path))
    with source as stream:
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
            expected_text = (row.get('expected_raw') or '').strip()
            expected_raw = None
            if expected_text:
                try:
                    expected_raw = int(expected_text, 0)
                except ValueError as exc:
                    raise ValueError(f'CSV row {row_number}: expected_raw must be a signed integer') from exc
            uniqueid = (row.get('uniqueid') or '').strip() or None
            address_text = (row.get('address') or '').strip()
            address = None
            if address_text:
                try:
                    address = int(address_text, 0)
                except ValueError as exc:
                    raise ValueError(f'CSV row {row_number}: address must be an XDF integer address') from exc
                if address < 0:
                    raise ValueError(f'CSV row {row_number}: address cannot be negative')
            flag_mask_text = (row.get('flag_mask') or '').strip()
            flag_mask = None
            if flag_mask_text:
                if kind != 'flag':
                    raise ValueError(f'CSV row {row_number}: flag_mask only applies to flags')
                try:
                    flag_mask = int(flag_mask_text, 0)
                except ValueError as exc:
                    raise ValueError(f'CSV row {row_number}: invalid flag_mask') from exc
                if not 0 < flag_mask <= 0xFF:
                    raise ValueError(f'CSV row {row_number}: flag_mask must fit one nonzero byte')
            result.append({'line': row_number, 'type': kind, 'name': name,
                           'row': r, 'col': c, 'value': value, 'raw': raw,
                           'expected_raw': expected_raw, 'uniqueid': uniqueid,
                           'address': address, 'flag_mask': flag_mask})
    if not result:
        raise ValueError('Edit CSV contains no operations')
    return result


def read_json_plan(json_path: str, default_map: str | None = None):
    """Parse a strict, hash-bound AI edit plan through the same CSV grammar.

    Returns (operations, pinned_bin_hash, pinned_xdf_hash). A JSON plan must
    specify the exact source pair, rather than relying on map-title matching.
    """
    def reject_constant(value):
        raise ValueError(f'JSON plan contains nonfinite numeric constant {value!r}')

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON plan key {key!r}')
            result[key] = value
        return result

    source = (open(json_path, 'r', encoding='utf-8-sig') if isinstance(json_path, (str, Path))
              else nullcontext(json_path))
    with source as stream:
        plan = json.load(stream, parse_constant=reject_constant,
                         object_pairs_hook=reject_duplicate_keys)
    if not isinstance(plan, dict) or set(plan) != {
            'schema', 'source_bin_sha256', 'xdf_sha256', 'operations'}:
        raise ValueError('JSON plan requires schema, source_bin_sha256, xdf_sha256, operations only')
    if plan['schema'] != 'kingai.xdf-batch-plan.v1':
        raise ValueError('Unsupported batch JSON plan schema')
    for name in ('source_bin_sha256', 'xdf_sha256'):
        if not isinstance(plan[name], str):
            raise ValueError(f'JSON plan {name} must be a 64-digit SHA-256 string')
        value = plan[name].strip()
        if len(value) != 64 or any(c not in '0123456789abcdefABCDEF' for c in value):
            raise ValueError(f'JSON plan {name} must be a 64-digit SHA-256 string')
    operations = plan['operations']
    if not isinstance(operations, list) or not operations:
        raise ValueError('JSON plan operations must be a nonempty array')

    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction='raise')
    writer.writeheader()
    for index, item in enumerate(operations, start=1):
        if not isinstance(item, dict) or set(item) - ALLOWED_COLUMNS:
            raise ValueError(f'JSON operation {index}: expected only supported edit fields')
        for key, value in item.items():
            if isinstance(value, (dict, list)) or isinstance(value, bool) and key != 'raw':
                raise ValueError(f'JSON operation {index}: invalid value type for {key}')
            if key == 'raw' and not isinstance(value, (bool, int, str, type(None))):
                raise ValueError(f'JSON operation {index}: raw must be a boolean or 0/1')
        writer.writerow({key: (str(value).lower() if isinstance(value, bool) else
                              '' if value is None else str(value))
                         for key, value in item.items()})
    buffer.seek(0)
    return (read_plan(buffer, default_map), plan['source_bin_sha256'], plan['xdf_sha256'])


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


def _check_expected_raw(op: dict, change: dict) -> None:
    """If supplied, match the exact original raw cell or containing flag byte."""
    expected = op.get('expected_raw')
    if expected is not None and change['old_raw'] != expected:
        raise ValueError(f"CSV row {op['line']}: {change['map']!r} old raw value changed: "
                         f"expected={expected}, actual={change['old_raw']}")


def _select_item(session, op: dict):
    """Select by title, optionally XDF uniqueid and XDF data address.

    Both selectors are AND constraints. Address is in the XDF's addressing
    space, not a file offset; no guessing or first-match fallback is allowed.
    """
    kind, name = op['type'], op['name']
    items = {'table': session.tables, 'scalar': session.constants,
             'flag': session.flags}[kind]
    matches = [item for item in items if item['title'] == name]
    if not matches:
        matches = [item for item in items if item['title'].casefold() == name.casefold()]
    uniqueid = op.get('uniqueid')
    if uniqueid is not None:
        if kind == 'flag':
            raise ValueError('Flag XDF uniqueid is not exposed by the pinned Exporter; '
                             'select by title and XDF address instead')
        matches = [item for item in matches if item.get('uniqueid') == uniqueid]
    address = op.get('address')
    if address is not None:
        matches = [item for item in matches if
                   (item.get('axes', {}).get('z', {}).get('address') if kind == 'table'
                    else item.get('address')) == address]
    flag_mask = op.get('flag_mask')
    if flag_mask is not None:
        matches = [item for item in matches if
                   type(item.get('mask')) is int and item['mask'] == flag_mask]
    if len(matches) > 1:
        raise ValueError(f"CSV row {op['line']}: ambiguous {kind} title {name!r}; "
                         'supply its XDF uniqueid, data address or flag_mask')
    if not matches:
        raise ValueError(f"CSV row {op['line']}: {kind} {name!r} not found with the supplied selectors")
    return matches[0]


def _stage_item(session, op: dict, parse_range, parse_flag_state,
                claims: dict, expectations: list, touched_tables: set):
    kind, name = op['type'], op['name']
    if kind == 'table':
        item = _select_item(session, op)
        rows, cols = session.get_table_dimensions(item)
        row_range, col_range = parse_range(op['row']), parse_range(op['col'])
        # Validate endpoints before expansion, so a typo cannot generate a huge loop.
        if (not row_range or not col_range or row_range.start < 1 or col_range.start < 1
                or row_range.stop - 1 > rows or col_range.stop - 1 > cols):
            raise ValueError(f"CSV row {op['line']}: cell selection outside {rows}x{cols} table")
        for row in row_range:
            for col in col_range:
                change = session.write_table_cell(item, row, col, op['value'], raw_mode=op['raw'])
                _check_expected_raw(op, change)
                _claim_bytes(change, item, claims)
                expectations.append((kind, item, row, col, change,
                                     _view_value(session, kind, item, row, col, change['new_raw'])))
        if id(item) not in touched_tables:
            session.add_table_log_entry(item['title'])
            touched_tables.add(id(item))
    elif kind == 'scalar':
        item = _select_item(session, op)
        change = session.write_scalar(item, op['value'], raw_mode=op['raw'])
        _check_expected_raw(op, change)
        _claim_bytes(change, item, claims)
        expectations.append((kind, item, 0, 0, change,
                             _view_value(session, kind, item)))
    else:
        item = _select_item(session, op)
        state = parse_flag_state(op['value'])
        change = session.write_flag(item, state)
        _check_expected_raw(op, change)
        _claim_bytes(change, item, claims)
        # Multi-bit flag clearing requires *all* masked bits to be zero.
        # A boolean read alone cannot distinguish partial clearance from full.
        mask = item.get('mask', 0x01)
        raw, observed = session.read_flag_state(item)
        if raw & mask != (mask if state else 0) or observed != state:
            raise ValueError(f"CSV row {op['line']}: incomplete flag mask write for {name!r}")
        expectations.append((kind, item, 0, 0, change, state))


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
            raw, actual = session.read_flag_state(item)
            mask = item.get('mask', 0x01)
            if raw & mask != (mask if view else 0) or actual != view:
                raise ValueError(f"Final flag mask changed for {item['title']!r}")
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
    json_path = getattr(args, 'plan_json', None)
    csv_path = getattr(args, 'csv', None)
    if bool(json_path) == bool(csv_path):
        raise ValueError('Supply exactly one batch input: --csv or --plan-json')
    pinned_bin, pinned_xdf = None, None
    source_path = json_path or csv_path
    # Parse exactly the bytes we identify in the receipt. Hashing a reopened
    # file after parsing can bind operations from plan A to the hash of plan B.
    plan_bytes, plan_hash = snapshot_plan(source_path)
    with io.StringIO(plan_bytes.decode('utf-8-sig'), newline='') as plan_stream:
        if json_path:
            plan, pinned_bin, pinned_xdf = read_json_plan(
                plan_stream, getattr(args, 'default_map', None))
        else:
            plan = read_plan(plan_stream, getattr(args, 'default_map', None))
    bin_hash = _sha256(args.bin)
    xdf_hash = _sha256(args.xdf)
    _require_hash('BIN', bin_hash, getattr(args, 'expected_bin_sha256', None))
    _require_hash('XDF', xdf_hash, getattr(args, 'expected_xdf_sha256', None))
    _require_hash('BIN', bin_hash, pinned_bin)
    _require_hash('XDF', xdf_hash, pinned_xdf)
    session = session_factory(args.xdf, args.bin)
    if not session.load():
        raise ValueError('Cannot load exact XDF/BIN pair')
    before = bytes(session.bin_data)
    if hashlib.sha256(before).hexdigest() != bin_hash:
        raise ValueError('BIN changed while loading; identity check failed')
    if _sha256(args.xdf) != xdf_hash or _sha256(source_path) != plan_hash:
        raise ValueError('XDF or plan changed while loading; identity check failed')
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
    bin_out, log_out = None, None
    if autosave:
        if (_sha256(args.bin) != bin_hash or _sha256(args.xdf) != xdf_hash
                or _sha256(source_path) != plan_hash):
            raise ValueError('Source BIN/XDF/plan changed while staging; refusing to save')
        bin_out, log_out = session.save_final(output_dir, 'batch')
        published = Path(bin_out).read_bytes()
        if published != after:
            raise ValueError('Published BIN differs from the validated staged image; treat save as invalid')

    if getattr(args, 'json', False):
        report = {
            'schema': 'kingai.xdf-batch.v1',
            'status': 'saved' if autosave else 'dry_run',
            'source_bin': {'name': Path(args.bin).name, 'size': len(before), 'sha256': bin_hash},
            'xdf': {'name': Path(args.xdf).name, 'sha256': xdf_hash},
            'plan': {'name': Path(source_path).name, 'sha256': plan_hash,
                     'format': 'json' if json_path else 'csv'},
            'csv_rows': len(plan) if not json_path else None,
            'plan_operations': len(plan), 'typed_targets': len(expectations),
            'changed_byte_count': len(changed),
            'proposed_bin_sha256': after_hash,
            'changes': session.changes,
            'changed_bytes': [{'file_offset': i, 'old_byte': before[i], 'new_byte': after[i]}
                              for i in changed],
            'saved_bin': bin_out, 'audit_log': log_out,
            'checksum_repaired': False, 'vehicle_validated': False,
        }
        print(json.dumps(report, indent=2, allow_nan=False))
    else:
        print(f'XDF SHA-256: {xdf_hash}')
        print(f'BIN SHA-256: {bin_hash}')
        print(f'Plan SHA-256: {plan_hash}')
        print(f'Operations: {len(plan)} plan operations; {len(expectations)} typed targets; '
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
            print(f'Saved new BIN: {bin_out}')
            print(f'Audit log: {log_out}')
            print('The saved image has not been checksum-repaired, flashed, or vehicle-validated.')
        else:
            print('DRY RUN: no BIN or audit files written; use --autosave --output-dir to publish.')
    return 0

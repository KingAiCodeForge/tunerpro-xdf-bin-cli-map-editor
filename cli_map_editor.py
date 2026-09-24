#!/usr/bin/env python3
"""
===============================================================================
 KingAI CLI Map Editor — AI-Friendly XDF + BIN Editor
===============================================================================

 Strict CLI tool for editing ECU calibration data using XDF definitions.
 Reuses UniversalXDFExporter for XDF/BIN parsing.
 Adds guarded individual edits and project-owned audit logs.

 Commands:
   list-maps    List all maps/tables/scalars/flags in an XDF
   show-map     Show a table's real values from the BIN
   show-scalar  Show a scalar's value
   show-flag    Show a bit flag's state and containing byte
   edit         Edit table cells (single or row/col ranges)
   edit-scalar  Edit a scalar value
   edit-flag    Set or clear one bit flag without changing sibling bits
   batch        Disabled pending transactional validation
   save         Disabled: unbound temp files cannot be persisted
   export       Snapshot XDF+BIN to an output directory
   port         Disabled pending verified transformations and transactional writes
   preflight    Validate XDF+BIN compatibility before editing
   diff         Show byte-level diff, optionally attributed through a TunerPro XDF
   apply-raw-patch   Apply an exact-hash, reversible raw-byte patch manifest
   verify-raw-patch  Verify and stage a raw-byte patch entirely in memory

 Author:       Jason King
 GitHub:       https://github.com/KingAiCodeForge
 Copyright:    (c) 2025 KingAI Pty Ltd

===============================================================================
"""

import argparse
import csv
import json
import io
import math
import os
import re
import struct
import sys
from datetime import datetime
from pathlib import Path
from contextlib import ExitStack, nullcontext
from typing import Any, Dict, List, Optional, Tuple

# Fix Windows console encoding (safe approach for Python 3.13+)
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Import the shared exporter engine
from tunerpro_exporter_for_cli_editor_version import UniversalXDFExporter
from tunerpro_xdf.xdf_addressing import table_layout
from tunerpro_xdf.xdf_equations import EquationError, inverse_affine
from tunerpro_xdf.xdf_values import read_integer, write_integer
from raw_patch_checksum_profiles import TRUSTED_CHECKSUM_VERIFIERS
from raw_patch_manifest import (
    PatchManifestError,
    apply_patch_manifest,
    verify_patch_manifest,
)

__version__ = "1.1.0"
__author__ = "Jason King"

# ═══════════════════════════════════════════════════════════════════════════════
# TIMESTAMP AND NAMING CONVENTIONS
# ═══════════════════════════════════════════════════════════════════════════════
# Output naming:  <original_name>_<operation>_<YYYYMMDD_HHMMSS>.bin
# Log naming:     <original_name>_<operation>_<YYYYMMDD_HHMMSS>.log
# Operations:     edited, ported, batch
# Legacy unbound temp-file persistence is disabled.

def _timestamp() -> str:
    """Generate timestamp string: YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _log_timestamp() -> str:
    """Generate the project log timestamp as MM/DD/YYYY HH:MM:SS."""
    return datetime.now().strftime("%m/%d/%Y %H:%M:%S")

def _output_name(bin_path: str, operation: str, ts: str) -> str:
    """Build output filename: <stem>_<operation>_<timestamp>.bin"""
    stem = Path(bin_path).stem
    return f"{stem}_{operation}_{ts}.bin"

def _log_name(bin_path: str, operation: str, ts: str) -> str:
    """Build log filename: <stem>_<operation>_<timestamp>.log"""
    stem = Path(bin_path).stem
    return f"{stem}_{operation}_{ts}.log"

def _format_raw_hex(raw: int, size_bits: int) -> str:
    """Format raw value as hex with proper width padding like TunerPro.
    1-byte -> 0x90, 2-byte -> 0x0384, 4-byte -> 0x00001234"""
    size_bytes = size_bits // 8
    hex_digits = size_bytes * 2
    if raw < 0:
        # Handle signed: show two's complement
        raw = raw & ((1 << size_bits) - 1)
    return f"0x{raw:0{hex_digits}X}"


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORTER WRAPPER — loads XDF + BIN via the shared engine
# ═══════════════════════════════════════════════════════════════════════════════

class XDFBinSession:
    """
    Session wrapper around UniversalXDFExporter.
    
    Provides:
    - Read access via the exporter's parsing engine
    - Write access via inverse math + direct byte writes
    - Change tracking for logging
    - Safe temp-file workflow
    """

    def __init__(self, xdf_path: str, bin_path: str):
        self.xdf_path = xdf_path
        self.bin_path = bin_path
        self.exporter = UniversalXDFExporter(xdf_path, bin_path)
        self.bin_data: Optional[bytearray] = None
        self.changes: List[Dict[str, Any]] = []  # Detailed cell-level
        self.log_entries: List[str] = []  # TunerPro-format log lines
        self._loaded = False

    def load(self) -> bool:
        """Load and parse XDF + BIN. Returns True on success."""
        if not self.exporter.validate_bin_file():
            return False
        if not self.exporter.parse_xdf():
            return False
        # Make a mutable copy of the bin data
        self.bin_data = bytearray(self.exporter.bin_data)
        self._loaded = True
        return True

    @property
    def tables(self) -> List[Dict]:
        return self.exporter.elements.get('tables', [])

    @property
    def constants(self) -> List[Dict]:
        return self.exporter.elements.get('constants', [])

    @property
    def flags(self) -> List[Dict]:
        return self.exporter.elements.get('flags', [])

    @property
    def patches(self) -> List[Dict]:
        return self.exporter.elements.get('patches', [])

    def find_table(self, name: str) -> Optional[Dict]:
        """Find a table by exact or case-insensitive title match."""
        return self._find_named(self.tables, name, 'table')

    def find_constant(self, name: str) -> Optional[Dict]:
        """Find a scalar/constant by title."""
        return self._find_named(self.constants, name, 'scalar')

    def find_flag(self, name: str) -> Optional[Dict]:
        """Find a bit flag by exact or case-insensitive title match."""
        return self._find_named(self.flags, name, 'flag')

    @staticmethod
    def _find_named(items, name, kind):
        matches = [item for item in items if item['title'] == name]
        if not matches:
            matches = [item for item in items if item['title'].casefold() == name.casefold()]
        if len(matches) > 1:
            raise ValueError(f'Ambiguous {kind} title {name!r}: {len(matches)} matching objects')
        return matches[0] if matches else None

    # ─── READ helpers ────────────────────────────────────────────────────

    def read_table_data(self, table: Dict) -> Optional[List[List[float]]]:
        """Read full table data using the exporter engine (real values)."""
        # Temporarily point exporter to our mutable bin_data
        original = self.exporter.bin_data
        self.exporter.bin_data = bytes(self.bin_data)
        try:
            return self.exporter._read_table_data(table)
        finally:
            self.exporter.bin_data = original

    def read_scalar_value(self, const: Dict) -> Tuple[Optional[int], Optional[float]]:
        """Read a scalar's raw and real value."""
        original = self.exporter.bin_data
        self.exporter.bin_data = bytes(self.bin_data)
        try:
            return self.exporter.read_constant(const)
        finally:
            self.exporter.bin_data = original

    def read_flag_state(self, flag: Dict) -> Tuple[int, bool]:
        """Read the containing byte and selected flag state."""
        address = flag['address']
        mask = flag.get('mask', 0x01)
        if not isinstance(mask, int) or mask <= 0 or mask > 0xFF:
            raise ValueError(f"Flag '{flag['title']}' has invalid mask {mask!r}")
        file_offset = self.exporter._xdf_addr_to_file_offset(address)
        raw = self._read_raw_at(file_offset, 8)
        return raw, bool(raw & mask)

    def _current_variables(self, item, table=None, row=0, col=0):
        original = self.exporter.bin_data
        self.exporter.bin_data = bytes(self.bin_data)
        try:
            linked = self.exporter.linked_vars_for(item)
            context = self.exporter.table_context(table, row, col) if table else None
            return self.exporter.math_variables(context, linked)
        finally:
            self.exporter.bin_data = original

    def get_table_dimensions(self, table: Dict) -> Tuple[int, int]:
        """Get (rows, cols) for a table."""
        z = table['axes'].get('z', {})
        y = table['axes'].get('y', {})
        x = table['axes'].get('x', {})
        rows = z.get('row_count', 1)
        cols = z.get('col_count', 1)
        if rows <= 1 and cols <= 1:
            rows = max(y.get('count', 1), 1)
            cols = max(x.get('count', 1), 1)
        return rows, cols

    # ─── WRITE helpers ───────────────────────────────────────────────────

    def _write_raw_at(self, file_offset: int, size_bits: int, value: int,
                      signed: bool = False, lsb_first: bool = False):
        """Write one bounded integer using the shared BIN implementation."""
        write_integer(self.bin_data, file_offset, size_bits, value, signed, lsb_first)

    def _read_raw_at(self, file_offset: int, size_bits: int,
                     signed: bool = False, lsb_first: bool = False) -> int:
        """Read one bounded integer using the shared BIN implementation."""
        return read_integer(self.bin_data, file_offset, size_bits, signed, lsb_first)

    def _inverse_math(self, equation: str, real_value: float,
                      linked_vars: Optional[Dict[str, float]] = None) -> Optional[int]:
        """Invert only equations proved affine by their parsed structure."""
        if any(name.lower() == 'x' for name in (linked_vars or {})):
            return None
        linked_names = {name.upper() for name in (linked_vars or {})}
        equation = re.sub(r'\bX\d+\b',
            lambda match: match.group() if match.group().upper() in linked_names else 'X',
            equation or '', flags=re.IGNORECASE)
        try:
            return inverse_affine(equation or "", real_value, linked_vars or {})
        except EquationError:
            return None

    def _raw_bounds(self, size_bits: int, signed: bool) -> Tuple[int, int]:
        """Get (min_raw, max_raw) for a given bit size and signedness."""
        if signed:
            return -(1 << (size_bits - 1)), (1 << (size_bits - 1)) - 1
        return 0, (1 << size_bits) - 1

    def _check_inverse_resolution(self, equation, raw, value, variables, bounds):
        """A symbolic affine expression can still collapse in floating arithmetic."""
        for neighbour in (raw - 1, raw + 1):
            if bounds[0] <= neighbour <= bounds[1]:
                adjacent, _ = self.exporter.evaluate_math(equation, neighbour, linked_vars=variables)
                if adjacent == value:
                    raise ValueError("Equation cannot distinguish adjacent raw values; supply an explicit raw value")

    def _staged_real(self, item, offset, size, raw, signed, lsb, predicted,
                     raw_mode, table=None, row=0, col=0):
        staged = bytearray(self.bin_data)
        write_integer(staged, offset, size, raw, signed, lsb)
        original = self.exporter.bin_data
        self.exporter.bin_data = staged
        try:
            context = self.exporter.table_context(table, row, col) if table else None
            actual, _ = self.exporter.evaluate_math(item.get('equation', ''), raw,
                context, linked_vars=self.exporter.linked_vars_for(item))
            if not raw_mode and actual != predicted:
                raise ValueError("Edit changes a conversion dependency; engineering write refused")
            return actual
        finally:
            self.exporter.bin_data = original

    def write_table_cell(self, table: Dict, row: int, col: int, real_value: float,
                         raw_mode: bool = False) -> Dict[str, Any]:
        """
        Write a single table cell. row/col are 1-based.
        
        Returns change record: {map, row, col, address, old_raw, new_raw, old_real, new_real}
        """
        z = table['axes'].get('z', {})
        xml = z.get('xml_element')
        if xml is not None and any(
            m.get('row') is not None or m.get('col') is not None
            for m in xml.findall('MATH')
        ):
            raise ValueError('Scoped table equations are read-only; audited scoped writes are not supported')
        rows, cols = self.get_table_dimensions(table)
        
        if not (1 <= row <= rows):
            raise IndexError(f"Row {row} out of range (1-{rows})")
        if not (1 <= col <= cols):
            raise IndexError(f"Col {col} out of range (1-{cols})")

        base_addr = z.get('address')
        if base_addr is None:
            raise ValueError(f"Table '{table['title']}' has no Z-axis address")

        size_bits = z.get('size_bits', 8)
        if z.get('type_flags', 0) & ~0x03:
            raise ValueError("This XDF storage type requires native TunerPro write parity")
        signed = z.get('signed', False)
        lsb_first = z.get('lsb_first', False)
        equation = z.get('equation', '')
        z_linked_vars = self._current_variables(z, table, row - 1, col - 1)

        if not math.isfinite(real_value):
            raise ValueError("Edit value must be finite")
        layout = table_layout(table)
        layout.validate_write()
        xdf_addr = layout.cell_address(row - 1, col - 1)
        file_offset = self.exporter._xdf_addr_to_file_offset(xdf_addr)

        # Read old value
        old_raw = self._read_raw_at(file_offset, size_bits, signed, lsb_first)
        old_real = float(old_raw)
        if equation:
            calc, _ = self.exporter.evaluate_math(equation, old_raw, linked_vars=z_linked_vars)
            if calc is not None:
                old_real = calc

        # Compute new raw
        if raw_mode:
            new_raw = int(round(real_value))
        else:
            new_raw = self._inverse_math(equation, real_value, linked_vars=z_linked_vars)
            if new_raw is None:
                raise ValueError(
                    f"Cannot convert real value {real_value} to raw "
                    f"for equation '{equation}'"
                )

        # Bounds check
        min_raw, max_raw = self._raw_bounds(size_bits, signed)
        if new_raw < min_raw or new_raw > max_raw:
            raise ValueError(
                f"Raw value {new_raw} out of range ({min_raw}..{max_raw}) "
                f"for {size_bits}-bit {'signed' if signed else 'unsigned'}"
            )

        # Compute written real for log accuracy
        new_real = float(new_raw)
        if equation:
            calc, _ = self.exporter.evaluate_math(equation, new_raw, linked_vars=z_linked_vars)
            if calc is not None:
                new_real = calc

        if not raw_mode:
            self._check_inverse_resolution(equation, new_raw, new_real, z_linked_vars, (min_raw, max_raw))
        new_real = self._staged_real(z, file_offset, size_bits, new_raw, signed,
            lsb_first, new_real, raw_mode, table, row - 1, col - 1)
        self._write_raw_at(file_offset, size_bits, new_raw, signed, lsb_first)
        change = {
            'map': table['title'],
            'type': 'table',
            'row': row,
            'col': col,
            'address': f"0x{xdf_addr:04X}",
            'file_offset': f"0x{file_offset:04X}",
            'old_raw': old_raw,
            'new_raw': new_raw,
            'old_real': round(old_real, 6),
            'new_real': round(new_real, 6),
            'size_bits': size_bits,
            'unit': z.get('unit', ''),
        }
        self.changes.append(change)
        return change

    def write_scalar(self, const: Dict, real_value: float,
                     raw_mode: bool = False) -> Dict[str, Any]:
        """
        Write a scalar value.
        
        Returns change record.
        """
        address = const['address']
        size_bits = const['size']
        if const.get('type_flags', 0) & ~0x03:
            raise ValueError("This XDF storage type requires native TunerPro write parity")
        signed = const.get('signed', False)
        lsb_first = const.get('lsb_first', False)
        equation = const.get('equation', '')
        linked_vars = self._current_variables(const)

        if not math.isfinite(real_value):
            raise ValueError("Edit value must be finite")
        file_offset = self.exporter._xdf_addr_to_file_offset(address)

        # Read old
        old_raw = self._read_raw_at(file_offset, size_bits, signed, lsb_first)
        old_real = float(old_raw)
        if equation:
            calc, _ = self.exporter.evaluate_math(equation, old_raw, linked_vars=linked_vars)
            if calc is not None:
                old_real = calc

        # Compute new raw
        if raw_mode:
            new_raw = int(round(real_value))
        else:
            new_raw = self._inverse_math(equation, real_value, linked_vars=linked_vars)
            if new_raw is None:
                raise ValueError(
                    f"Cannot convert real value {real_value} to raw "
                    f"for equation '{equation}'"
                )

        # Bounds check
        min_raw, max_raw = self._raw_bounds(size_bits, signed)
        if new_raw < min_raw or new_raw > max_raw:
            raise ValueError(
                f"Raw value {new_raw} out of range ({min_raw}..{max_raw})"
            )

        # Compute written real
        new_real = float(new_raw)
        if equation:
            calc, _ = self.exporter.evaluate_math(equation, new_raw, linked_vars=linked_vars)
            if calc is not None:
                new_real = calc

        if not raw_mode:
            self._check_inverse_resolution(equation, new_raw, new_real, linked_vars, (min_raw, max_raw))
        new_real = self._staged_real(const, file_offset, size_bits, new_raw, signed,
            lsb_first, new_real, raw_mode)
        unit = const.get('unit', '')
        hex_old = _format_raw_hex(old_raw, size_bits)
        hex_new = _format_raw_hex(new_raw, size_bits)
        dp = const.get('decimalpl', 2)

        # TunerPro-format scalar log entry:
        # MM/DD/YYYY HH:MM:SS  Scalar:    name changed from VAL UNIT (0xHEX) to VAL UNIT (0xHEX).
        ts = _log_timestamp()
        if unit:
            entry = (
                f"{ts}  Scalar:    {const['title']} changed "
                f"from {old_real:.{dp}f} {unit} ({hex_old}) "
                f"to {new_real:.{dp}f} {unit} ({hex_new})."
            )
        else:
            entry = (
                f"{ts}  Scalar:    {const['title']} changed "
                f"from {old_real:.{dp}f} ({hex_old}) "
                f"to {new_real:.{dp}f} ({hex_new})."
            )
        change = {
            'map': const['title'],
            'type': 'scalar',
            'row': '',
            'col': '',
            'address': f"0x{address:04X}",
            'file_offset': f"0x{file_offset:04X}",
            'old_raw': old_raw,
            'new_raw': new_raw,
            'old_real': round(old_real, 6),
            'new_real': round(new_real, 6),
            'size_bits': size_bits,
            'unit': unit,
        }
        # Construct the audit entry before touching bytes: invalid formatting
        # metadata must not leave an unrecorded edit in the session.
        self._write_raw_at(file_offset, size_bits, new_raw, signed, lsb_first)
        self.log_entries.append(entry)
        self.changes.append(change)
        return change

    def write_flag(self, flag: Dict, state: bool) -> Dict[str, Any]:
        """Set or clear one XDF flag while preserving every sibling bit."""
        address = flag['address']
        mask = flag.get('mask', 0x01)
        if not isinstance(mask, int) or mask <= 0 or mask > 0xFF:
            raise ValueError(f"Flag '{flag['title']}' has invalid mask {mask!r}")

        file_offset = self.exporter._xdf_addr_to_file_offset(address)
        old_raw = self._read_raw_at(file_offset, 8)
        old_state = bool(old_raw & mask)
        new_raw = (old_raw | mask) if state else (old_raw & (~mask & 0xFF))
        self._write_raw_at(file_offset, 8, new_raw)

        self.add_flag_log_entry(
            flag['title'],
            "Set" if old_state else "Not Set",
            "Set" if state else "Not Set",
        )
        change = {
            'map': flag['title'],
            'type': 'flag',
            'row': '',
            'col': '',
            'address': f"0x{address:04X}",
            'file_offset': f"0x{file_offset:04X}",
            'old_raw': old_raw,
            'new_raw': new_raw,
            'old_real': int(old_state),
            'new_real': int(state),
            'size_bits': 8,
            'unit': f"mask=0x{mask:02X}",
        }
        self.changes.append(change)
        return change

    # ─── TEMP FILE / SAVE ────────────────────────────────────────────────

    def save_temp(self):
        """Unbound temp BIN files cannot safely preserve edit provenance."""
        raise ValueError('Temporary saves are disabled; use --autosave --output-dir for a new BIN and audit logs')

    def save_final(self, output_dir: str,
                   operation: str = "edited") -> Tuple[str, str]:
        """
        Save to final named file with timestamp + matching log.

        Writes BOTH:
        - Project-owned .log (human-readable; not a native TunerPro log)
        - Detailed .csv (cell-level data for auditing/automation)

        Returns (bin_path, log_path).
        """
        ts = _timestamp()
        bin_name = _output_name(self.bin_path, operation, ts)
        log_name = _log_name(self.bin_path, operation, ts)
        detail_name = log_name.replace('.log', '_detailed.csv')

        bin_out = os.path.join(output_dir, bin_name)
        log_out = os.path.join(output_dir, log_name)
        detail_out = os.path.join(output_dir, detail_name)
        output_paths = [Path(path) for path in (bin_out, log_out, detail_out)]
        protected = {Path(self.bin_path).resolve(), Path(self.xdf_path).resolve()}
        resolved = [path.resolve() for path in output_paths]
        if len(set(resolved)) != len(resolved) or any(path in protected for path in resolved):
            raise ValueError('Output paths must be distinct from each other and the input files')
        for path in output_paths:
            if os.path.lexists(path):
                raise FileExistsError(f'Refusing to overwrite existing output: {path}')

        # Render the audit files before creating anything, so malformed log
        # metadata cannot leave a BIN without its corresponding audit content.
        log_buffer, detail_buffer = io.StringIO(), io.StringIO(newline='')
        self._write_log(log_out, log_buffer)
        self._write_detailed_log(detail_out, detail_buffer)
        payloads = [bytes(self.bin_data), log_buffer.getvalue().encode('utf-8'),
                    detail_buffer.getvalue().encode('utf-8')]
        os.makedirs(output_dir, exist_ok=True)
        # Exclusive creation also protects against collisions after preflight.
        # Reserve all paths before writing bytes; preserve reservations on an
        # I/O error rather than deleting any files. The caller reports failure.
        with ExitStack() as stack:
            handles = [stack.enter_context(open(path, 'xb')) for path in output_paths]
            for index in (1, 2, 0):
                handles[index].write(payloads[index])
        return bin_out, log_out

    def add_table_log_entry(self, table_title: str):
        """Add a TunerPro-format table log entry.
        TunerPro just says 'changed.' for tables - no cell detail."""
        ts = _log_timestamp()
        entry = f"{ts}  Table:     {table_title} changed."
        self.log_entries.append(entry)

    def add_flag_log_entry(self, flag_title: str,
                           old_state: str, new_state: str):
        """Add a TunerPro-format flag log entry.
        TunerPro ends flag entries with double period '..'"""
        ts = _log_timestamp()
        entry = (f"{ts}  Flag:      {flag_title} "
                 f"changed from {old_state} to {new_state}..")
        self.log_entries.append(entry)

    def add_patch_log_entry(self, patch_title: str,
                            prefix: str = "PATCH"):
        """Add a TunerPro-format patch log entry."""
        ts = _log_timestamp()
        entry = (f"{ts}  Patch:     "
                 f"[{prefix}] {patch_title} changed.")
        self.log_entries.append(entry)

    def _write_log(self, log_path: str, stream=None):
        """
        Write the KingAI project change log.

        Verified against 54 real TunerPro .log files across:
          BMW MS40, MS42, MS43 | Holden VS, VT, VY | OSE V8

        Project header (3 lines):
          KingAI CLI Map Editor audit log for <filename>.
          Generated by cli_map_editor.py; this is not a native TunerPro log.
          **************************************************************************

        Type column alignment (TunerPro pads type label to col 10):
          Table:     <name> changed.
          Scalar:    <name> changed from <old> <UNIT> (0xHH) to <new> <UNIT> (0xHH).
          Flag:      <name> changed from Not Set to Set..
          Patch:     [PATCH] <name> changed.

        Unit formatting (pass-through from XDF, no transformation):
          BMW XDFs use brackets:  [°C]  [km/h]  [-]  [U/min]
          Holden XDFs use plain:  DEG  RPM  KPH  MSEC/ GRAM  DEG C

        Hex formatting (variable width, uppercase, 0x prefix):
          8-bit:  0x90  0xFF  0x00
          16-bit: 0x0384  0x02D8  0x1CE8

        Flag entries end with double period:  Set..  Not Set..
        """
        bin_filename = os.path.basename(self.bin_path)
        with (open(log_path, 'x', encoding='utf-8') if stream is None else nullcontext(stream)) as f:
            f.write(f"KingAI CLI Map Editor audit log for {bin_filename}.\n")
            f.write("Generated by cli_map_editor.py; "
                    "this is not a native TunerPro log.\n")
            f.write("*" * 74 + "\n")
            # Write all log entries in chronological order
            for entry in self.log_entries:
                f.write(entry + "\n")
            # KingAI extended detail section (after TunerPro section)
            if self.changes:
                f.write("\n")
                f.write("=" * 74 + "\n")
                f.write("KingAI CLI Map Editor — Extended Detail\n")
                f.write("=" * 74 + "\n")
                for c in self.changes:
                    if c['type'] == 'table':
                        f.write(
                            f"  {c['map']}[{c['row']},{c['col']}] "
                            f"addr={c['address']} "
                            f"file={c['file_offset']} "
                            f"old_raw={c['old_raw']} "
                            f"new_raw={c['new_raw']} "
                            f"old={c['old_real']} "
                            f"new={c['new_real']}\n"
                        )
                    elif c['type'] in ('scalar', 'flag'):
                        f.write(
                            f"  {c['map']} "
                            f"addr={c['address']} "
                            f"file={c['file_offset']} "
                            f"old_raw={c['old_raw']} "
                            f"new_raw={c['new_raw']} "
                            f"old={c['old_real']} "
                            f"new={c['new_real']} "
                            f"{c.get('unit', '')}\n"
                        )

    def _write_detailed_log(self, log_path: str, stream=None):
        """
        Write detailed cell-level change log (CSV format).
        Extended format with per-cell data for auditing.

        Columns beyond TunerPro's format:
          FILE_OFFSET — actual byte position in BIN
          OLD_HEX / NEW_HEX — raw values in hex
          SIZE_BITS — 8/16/32
          EQUATION — forward equation from XDF
        """
        with (open(log_path, 'x', newline='', encoding='utf-8') if stream is None else nullcontext(stream)) as f:
            writer = csv.writer(f)
            writer.writerow([
                'TIMESTAMP', 'MAP_NAME', 'TYPE',
                'ROW', 'COLUMN',
                'ADDRESS', 'FILE_OFFSET',
                'OLD_RAW', 'NEW_RAW',
                'OLD_HEX', 'NEW_HEX',
                'OLD_REAL', 'NEW_REAL',
                'UNIT', 'SIZE_BITS'
            ])
            ts = _log_timestamp()
            for c in self.changes:
                sb = c.get('size_bits', 8)
                writer.writerow([
                    ts,
                    c['map'], c['type'],
                    c['row'], c['col'],
                    c['address'], c['file_offset'],
                    c['old_raw'], c['new_raw'],
                    _format_raw_hex(c['old_raw'], sb),
                    _format_raw_hex(c['new_raw'], sb),
                    c['old_real'], c['new_real'],
                    c.get('unit', ''), sb
                ])


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT DETECTION AND AFR/LAMBDA CONVERSION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_unit_type(name: str, unit: str = "") -> str:
    """
    Detect map Z-axis unit type from the Z-axis unit string and table name.
    
    Only classifies based on the Z-axis OUTPUT unit (what the table values represent),
    NOT based on axis labels like RPM or MAF that appear in the table name.
    
    Returns: 'lambda', 'afr', 'mass', or 'unknown'
    """
    unit_lower = unit.lower().strip()
    name_lower = name.lower()
    
    # Check Z-axis unit string first (most reliable)
    if any(kw in unit_lower for kw in ['lambda', 'lamda', 'lam']):
        return 'lambda'
    if any(kw in unit_lower for kw in ['afr', 'air/fuel', 'a/f ratio']):
        return 'afr'
    if any(kw in unit_lower for kw in ['mg/', 'g/s', 'kg/h', 'cylair']):
        return 'mass'
    
    # Check table name — but only for Z-axis type keywords, not axis labels
    # Tables like ip_iga_maf_n__n__maf are IGNITION tables indexed by MAF,
    # not mass-output tables. Only flag if name suggests Z-axis IS mass.
    # e.g. id_maf_tab (the MAF calibration table itself outputs kg/h)
    if name_lower.startswith('id_maf_tab') or name_lower in ('ip_tib__n__maf',):
        return 'mass'
    if any(kw in name_lower for kw in ['lambda', 'lamda']):
        return 'lambda'
    if any(kw in name_lower for kw in ['_lam_', 'lam_i_', 'lam_neg_', 'lam_pos_']):
        return 'lambda'
    if any(kw in name_lower for kw in ['afr', 'air_fuel', 'airfuel']):
        return 'afr'
    
    return 'unknown'


def afr_to_lambda(afr: float, stoich: float = 14.7) -> float:
    return afr / stoich

def lambda_to_afr(lmb: float, stoich: float = 14.7) -> float:
    return lmb * stoich


# ═══════════════════════════════════════════════════════════════════════════════
# PORTING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def bilinear_resample(src_mat: List[List[float]],
                      src_x: List[float], src_y: List[float],
                      dst_x: List[float], dst_y: List[float]) -> List[List[float]]:
    """
    Resample a 2D table using bilinear interpolation.
    src_mat: [rows][cols] of float values
    src_x: col-axis values (len = src_cols)
    src_y: row-axis values (len = src_rows)
    dst_x/dst_y: target axis values
    """
    src_rows = len(src_mat)
    src_cols = len(src_mat[0]) if src_rows > 0 else 0

    def find_interval(axis, v):
        if v <= axis[0]:
            return 0, 0.0
        if v >= axis[-1]:
            return len(axis) - 2, 1.0
        for i in range(len(axis) - 1):
            if axis[i] <= v <= axis[i + 1]:
                denom = axis[i + 1] - axis[i]
                t = (v - axis[i]) / denom if denom != 0 else 0.0
                return i, t
        return len(axis) - 2, 1.0

    dst_rows = len(dst_y)
    dst_cols = len(dst_x)
    result = []
    for ry in range(dst_rows):
        row_out = []
        iy, ty = find_interval(src_y, dst_y[ry])
        iy1 = min(iy + 1, src_rows - 1)
        for cx in range(dst_cols):
            ix, tx = find_interval(src_x, dst_x[cx])
            ix1 = min(ix + 1, src_cols - 1)
            v00 = src_mat[iy][ix]
            v01 = src_mat[iy][ix1]
            v10 = src_mat[iy1][ix]
            v11 = src_mat[iy1][ix1]
            top = v00 * (1 - tx) + v01 * tx
            bot = v10 * (1 - tx) + v11 * tx
            val = top * (1 - ty) + bot * ty
            row_out.append(val)
        result.append(row_out)
    return result


def axis_or_index(labels: Optional[List[float]], length: int) -> List[float]:
    """Return axis labels or generate 0..n-1 index."""
    if labels and len(labels) == length:
        return [float(v) for v in labels]
    return [float(i) for i in range(length)]


# ═══════════════════════════════════════════════════════════════════════════════
# RANGE PARSING
# ═══════════════════════════════════════════════════════════════════════════════

def parse_range(s: str) -> range:
    """
    Parse '3' or '1-5' into a range (inclusive, 1-based).
    Returns range(start, end+1).
    """
    s = s.strip()
    if '-' in s:
        parts = s.split('-', 1)
        start = int(parts[0])
        end = int(parts[1])
        if start > end:
            raise ValueError(f"Invalid range: {s} (start > end)")
        return range(start, end + 1)
    v = int(s)
    return range(v, v + 1)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_list_maps(args):
    """List all maps, scalars, flags, and patches in the XDF."""
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    # Tables
    print(f"\n{'='*70}")
    print(f"TABLES ({len(session.tables)})")
    print(f"{'='*70}")
    for t in session.tables:
        rows, cols = session.get_table_dimensions(t)
        z = t['axes'].get('z', {})
        addr = z.get('address')
        addr_str = f"0x{addr:04X}" if addr is not None else "N/A"
        unit = z.get('unit', '')
        eq = z.get('equation', '') or 'X'
        print(f"  {t['title']}")
        print(f"    {rows}x{cols}  addr={addr_str}  unit={unit}  eq={eq}")

    # Scalars
    print(f"\n{'='*70}")
    print(f"SCALARS ({len(session.constants)})")
    print(f"{'='*70}")
    for c in session.constants:
        addr = f"0x{c['address']:04X}" if c['address'] is not None else "N/A"
        try:
            raw, real = session.read_scalar_value(c)
            val_str = f"{real}" if real is not None else "ERROR"
        except (EquationError, ValueError, TypeError, KeyError) as exc:
            val_str = f"ERROR ({exc})"
        unit = c.get('unit', '')
        print(f"  {c['title']}: {val_str} {unit}  [addr={addr}]")

    # Flags
    if session.flags:
        print(f"\n{'='*70}")
        print(f"FLAGS ({len(session.flags)})")
        print(f"{'='*70}")
        for f in session.flags:
            raw, is_set = session.read_flag_state(f)
            print(
                f"  {f['title']}: {'Set' if is_set else 'Not Set'}  "
                f"[addr=0x{f['address']:04X}, mask=0x{f['mask']:02X}, "
                f"byte=0x{raw:02X}]"
            )

    # Patches
    if session.patches:
        print(f"\n{'='*70}")
        print(f"PATCHES ({len(session.patches)})")
        print(f"{'='*70}")
        applied = sum(1 for p in session.patches if p['status'] == 'applied')
        print(f"  Applied: {applied} / {len(session.patches)}")
        for p in session.patches:
            status = {'applied': '[APPLIED]', 'not_applied': '[NOT APPLIED]',
                      'partial': '[PARTIAL]', 'unknown': '[UNKNOWN]'}
            print(f"  {status.get(p['status'], '?')} {p['title']}")

    print()
    return 0


def _label_is_nonnumeric(value: Any) -> bool:
    """Return True when an XDF LABEL is text rather than a numeric literal."""

    if value is None or str(value).strip() == "":
        return False
    try:
        float(str(value).strip())
    except ValueError:
        return True
    return False


def cmd_show_map(args):
    """Show a single table's real values."""
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    table = session.find_table(args.map)
    if table is None:
        print(f"ERROR: Table '{args.map}' not found in XDF")
        print("Available tables:")
        for t in session.tables:
            print(f"  {t['title']}")
        return 1

    rows, cols = session.get_table_dimensions(table)
    z = table['axes'].get('z', {})
    x = table['axes'].get('x', {})
    y = table['axes'].get('y', {})
    decimalpl = z.get('decimalpl', 2)

    print(f"\nTABLE: {table['title']}")
    print(f"  Category: {table['category']}")
    print(f"  Dimensions: {rows} rows x {cols} cols")
    print(f"  Z-Axis address: 0x{z.get('address', 0):04X}")
    print(f"  Z-Axis equation: {z.get('equation', 'X')}")
    print(f"  Z-Axis unit: {z.get('unit', '')}")

    # Show axes
    x_labels = x.get('labels', [])
    y_labels = y.get('labels', [])
    x_display_labels = x.get('display_labels', [])
    y_display_labels = y.get('display_labels', [])
    x_has_text_labels = any(
        _label_is_nonnumeric(value) for value in x_display_labels
    )
    y_has_text_labels = any(
        _label_is_nonnumeric(value) for value in y_display_labels
    )
    if x_labels:
        x_dp = x.get('decimalpl', 2)
        qualifier = " numeric rendering" if x_has_text_labels else ""
        print(
            f"  X-Axis{qualifier} ({x.get('unit', '')}): "
            f"[{', '.join(f'{v:.{x_dp}f}' for v in x_labels)}]"
        )
    if x_has_text_labels:
        print(
            "  X-Axis raw XDF labels: "
            + json.dumps(x_display_labels, ensure_ascii=False)
        )
    if y_labels:
        y_dp = y.get('decimalpl', 2)
        qualifier = " numeric rendering" if y_has_text_labels else ""
        print(
            f"  Y-Axis{qualifier} ({y.get('unit', '')}): "
            f"[{', '.join(f'{v:.{y_dp}f}' for v in y_labels)}]"
        )
    if y_has_text_labels:
        print(
            "  Y-Axis raw XDF labels: "
            + json.dumps(y_display_labels, ensure_ascii=False)
        )

    # Read data
    data = session.read_table_data(table)
    if data is None:
        print("  ERROR: Could not read table data")
        return 1

    # Print matrix
    print(f"\n  Data ({rows}x{cols}):")
    col_width = max(8, decimalpl + 5)

    # X-axis header row
    if x_labels:
        header = "         "
        for c, xl in enumerate(x_labels[:cols]):
            header += f"{xl:>{col_width}.{x.get('decimalpl', 2)}f}"
        print(header)

    for r, row in enumerate(data):
        y_lbl = ""
        if y_labels and r < len(y_labels) and not y_has_text_labels:
            y_dp = y.get('decimalpl', 2)
            y_lbl = f"{y_labels[r]:>8.{y_dp}f} "
        else:
            y_lbl = f"  Row {r}: "
        vals = "".join(f"{v:>{col_width}.{decimalpl}f}" for v in row)
        print(f"  {y_lbl}{vals}")

    print()
    return 0


def cmd_show_scalar(args):
    """Show a single scalar's value."""
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    const = session.find_constant(args.name)
    if const is None:
        print(f"ERROR: Scalar '{args.name}' not found")
        return 1

    raw, real = session.read_scalar_value(const)
    dp = const.get('decimalpl', 2)
    print(f"\nSCALAR: {const['title']}")
    print(f"  Value: {real:.{dp}f} {const.get('unit', '')}")
    print(f"  Raw: {raw}")
    print(f"  Address: 0x{const['address']:04X}")
    print(f"  Equation: {const.get('equation', 'X')}")
    print()
    return 0


def cmd_show_flag(args):
    """Show one flag's state and its containing byte."""
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    flag = session.find_flag(args.name)
    if flag is None:
        print(f"ERROR: Flag '{args.name}' not found")
        return 1

    raw, is_set = session.read_flag_state(flag)
    mask = flag.get('mask', 0x01)
    print(f"\nFLAG: {flag['title']}")
    print(f"  State: {'Set' if is_set else 'Not Set'}")
    print(f"  Address: 0x{flag['address']:04X}")
    print(f"  Mask: 0x{mask:02X}")
    print(f"  Containing byte: 0x{raw:02X}")
    print()
    return 0


def _require_autosave(args):
    if not getattr(args, 'autosave', False) or not getattr(args, 'output_dir', None):
        print('ERROR: Edits require --autosave --output-dir <directory> to create a new BIN and audit logs.')
        print('Use the saved BIN as --bin for a subsequent edit; temporary sessions are disabled.')
        return False
    return True


def cmd_edit(args):
    """Edit table cells — single or range."""
    if not _require_autosave(args):
        return 1
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    table = session.find_table(args.map)
    if table is None:
        print(f"ERROR: Table '{args.map}' not found")
        return 1

    rows_range = parse_range(args.rows)
    cols_range = parse_range(args.cols)
    raw_mode = getattr(args, 'raw', False)

    count = 0
    for r in rows_range:
        for c in cols_range:
            change = session.write_table_cell(
                table, r, c, args.value, raw_mode=raw_mode)
            print(
                f"  {change['map']}[{r},{c}] "
                f"addr={change['address']} "
                f"old_raw={change['old_raw']} "
                f"new_raw={change['new_raw']} "
                f"old_real={change['old_real']} "
                f"new_real={change['new_real']}")
            count += 1

    # TunerPro-format: one log entry per table edit command
    session.add_table_log_entry(table['title'])

    bin_out, log_out = session.save_final(args.output_dir, 'edited')
    print(f"\nEdited {count} cells. Saved: {bin_out}")
    print(f"Log:   {log_out}")

    return 0


def cmd_edit_scalar(args):
    """Edit a scalar value."""
    if not _require_autosave(args):
        return 1
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    const = session.find_constant(args.name)
    if const is None:
        print(f"ERROR: Scalar '{args.name}' not found")
        return 1

    raw_mode = getattr(args, 'raw', False)
    change = session.write_scalar(const, args.value, raw_mode=raw_mode)
    print(f"  {change['map']} addr={change['address']} "
          f"old_raw={change['old_raw']} new_raw={change['new_raw']} "
          f"old_real={change['old_real']} new_real={change['new_real']}")

    bin_out, log_out = session.save_final(args.output_dir, 'edited')
    print(f"Saved: {bin_out}")
    print(f"Log:   {log_out}")

    return 0


def _parse_flag_state(value: Any) -> bool:
    """Parse explicit CLI/CSV flag states without Python truthiness traps."""
    normalized = str(value).strip().lower()
    if normalized in {'1', 'set', 'on', 'true', 'yes', 'enabled', 'enable'}:
        return True
    if normalized in {'0', 'clear', 'off', 'false', 'no', 'disabled', 'disable'}:
        return False
    raise ValueError(
        f"Invalid flag state {value!r}; use set/clear, on/off, true/false, or 1/0"
    )


def cmd_edit_flag(args):
    """Set or clear one bit flag."""
    if not _require_autosave(args):
        return 1
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    flag = session.find_flag(args.name)
    if flag is None:
        print(f"ERROR: Flag '{args.name}' not found")
        return 1

    state = _parse_flag_state(args.state)
    change = session.write_flag(flag, state)
    print(
        f"  {change['map']} addr={change['address']} "
        f"mask={change['unit']} old_byte=0x{change['old_raw']:02X} "
        f"new_byte=0x{change['new_raw']:02X} "
        f"state={'Set' if state else 'Not Set'}"
    )

    bin_out, log_out = session.save_final(args.output_dir, 'edited')
    print(f"Saved: {bin_out}")
    print(f"Log:   {log_out}")
    return 0


def cmd_batch(args):
    """Refuse batch writes until transactional validation is supported."""
    print('ERROR: Batch writes are disabled until all-row validation and transactional saves are implemented.')
    print('Use individual edit commands with --autosave --output-dir, then use the resulting BIN for the next edit.')
    return 1


def cmd_save(args):
    """Refuse unbound temp-file persistence."""
    print('ERROR: Standalone save is disabled because legacy temp files are not bound to their source BIN and XDF.')
    print('Repeat the intended edit with --autosave --output-dir to create a new BIN and audit logs.')
    return 1


def cmd_port(args):
    """Refuse unverified automatic map transformations."""
    print('ERROR: Map porting is disabled until axis/unit compatibility and transactional writes are verified.')
    print('Use show-map and diff to review the inputs; apply only individually verified edits with --autosave.')
    return 1


def cmd_preflight(args):
    """Validate XDF+BIN compatibility."""
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("FAIL: Cannot load XDF+BIN")
        return 1

    issues = []
    info = []

    # Check base offset
    bo = session.exporter.base_offset
    bs = session.exporter.base_subtract
    info.append(f"BASEOFFSET: 0x{bo:X} subtract={bs}")
    info.append(f"BIN size: {len(session.bin_data)} bytes ({len(session.bin_data)//1024}KB)")
    info.append(f"Definition: {session.exporter.definition_name}")

    # Check tables
    tables_ok = 0
    tables_bad = 0
    address_ranges = []

    for const in session.constants:
        try:
            session.read_scalar_value(const)
        except (ValueError, IndexError) as exc:
            issues.append(f"Scalar '{const['title']}': {exc}")
    for flag in session.flags:
        if session.exporter.read_value_from_bin(flag['address'], 8) is None:
            issues.append(f"Flag '{flag['title']}' cannot be read")

    for t in session.tables:
        rows, cols = session.get_table_dimensions(t)
        z = t['axes'].get('z', {})
        addr = z.get('address')
        if addr is None:
            issues.append(f"Table '{t['title']}' has no Z-axis address")
            tables_bad += 1
            continue

        try:
            layout = table_layout(t)
            file_start, file_end = layout.file_span(bo, bs)
        except (ValueError, IndexError) as exc:
            issues.append(f"Table '{t['title']}': {exc}")
            tables_bad += 1
            continue

        if file_start < 0 or file_end > len(session.bin_data):
            issues.append(
                f"Table '{t['title']}' extends past BIN end "
                f"(0x{file_start:X}..0x{file_end:X} > 0x{len(session.bin_data):X})"
            )
            tables_bad += 1
            continue

        address_ranges.append((file_start, file_end, t['title']))

        # Read validation is separate from native TunerPro write parity.
        try:
            data = session.read_table_data(t)
        except (ValueError, IndexError) as exc:
            issues.append(f"Table '{t['title']}': {exc}")
            tables_bad += 1
            continue
        if data is not None and len(data) > 0 and len(data[0]) > 0:
            tables_ok += 1
        else:
            issues.append(f"Table '{t['title']}' cannot be read")
            tables_bad += 1

    # Check for overlaps
    address_ranges.sort(key=lambda x: x[0])
    for i in range(len(address_ranges) - 1):
        _, end_a, name_a = address_ranges[i]
        start_b, _, name_b = address_ranges[i + 1]
        if end_a > start_b:
            issues.append(f"OVERLAP: '{name_a}' and '{name_b}' share address space")

    # Print results
    print(f"\n{'='*60}")
    print(f"PREFLIGHT CHECK: {args.xdf}")
    print(f"{'='*60}")
    for line in info:
        print(f"  {line}")
    print(f"\n  Tables: {tables_ok} OK, {tables_bad} issues")
    print(f"  Scalars: {len(session.constants)}")
    print(f"  Flags: {len(session.flags)}")
    print(f"  Patches: {len(session.patches)}")

    if issues:
        print(f"\n  ISSUES ({len(issues)}):")
        for issue in issues:
            print(f"    ! {issue}")
        print()
        return 1
    else:
        print(f"\n  ALL CHECKS PASSED")
        print()
        return 0


def _xdf_owner_label(owner: Dict[str, Any]) -> str:
    """Format one parsed TunerPro XDF owner for diff output."""
    label = f"{owner['kind']}:{owner['title']}"
    if owner.get('cell'):
        row, col = owner['cell']
        label += f" [row={row},col={col}]"
    if owner.get('entry'):
        label += f" [{owner['entry']}]"
    return label


def _attribute_xdf_differences(session: XDFBinSession, changed_offsets) -> Tuple[Dict[int, List[Dict]], List[str]]:
    """Map changed file offsets to parsed TunerPro XDF items without guessing."""
    wanted = set(changed_offsets)
    owners: Dict[int, List[Dict[str, Any]]] = {}
    warnings: List[str] = []

    def add_owner(offset: int, owner: Dict[str, Any]):
        if offset not in wanted:
            return
        existing = owners.setdefault(offset, [])
        identity = (
            owner.get('kind'), owner.get('title'), owner.get('uniqueid'),
            owner.get('cell'), owner.get('entry'),
        )
        if not any((
            item.get('kind'), item.get('title'), item.get('uniqueid'),
            item.get('cell'), item.get('entry'),
        ) == identity for item in existing):
            existing.append(owner)

    def translated(address: int) -> int:
        return session.exporter._xdf_addr_to_file_offset(address)

    for table in session.tables:
        title = table.get('title') or '<untitled table>'
        try:
            layout = table_layout(table)
            start, end = layout.file_span(
                session.exporter.base_offset, session.exporter.base_subtract)
            if not any(start <= offset < end for offset in wanted):
                continue
            for row in range(layout.rows):
                for col in range(layout.cols):
                    offset = translated(layout.cell_address(row, col))
                    for byte_offset in range(offset, offset + layout.width):
                        add_owner(byte_offset, {
                            'kind': 'table',
                            'title': title,
                            'uniqueid': table.get('uniqueid'),
                            'cell': (row + 1, col + 1),
                        })
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            warnings.append(f"table '{title}': {exc}")

    for const in session.constants:
        title = const.get('title') or '<untitled scalar>'
        try:
            size_bits = int(const.get('size', 8))
            if size_bits <= 0 or size_bits % 8:
                raise ValueError(f"unsupported element width {size_bits} bits")
            offset = translated(int(const['address']))
            for byte_offset in range(offset, offset + size_bits // 8):
                add_owner(byte_offset, {
                    'kind': 'scalar',
                    'title': title,
                    'uniqueid': const.get('uniqueid'),
                })
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append(f"scalar '{title}': {exc}")

    for flag in session.flags:
        title = flag.get('title') or '<untitled flag>'
        try:
            add_owner(translated(int(flag['address'])), {
                'kind': 'flag',
                'title': title,
                'uniqueid': flag.get('uniqueid'),
            })
        except (KeyError, TypeError, ValueError) as exc:
            warnings.append(f"flag '{title}': {exc}")

    for patch in session.patches:
        title = patch.get('title') or '<untitled patch>'
        for entry in patch.get('entries', []):
            entry_name = entry.get('name') or '<unnamed entry>'
            try:
                size_bytes = int(entry['datasize'])
                if size_bytes <= 0:
                    raise ValueError(f"invalid data size {size_bytes}")
                offset = translated(int(entry['address']))
                for byte_offset in range(offset, offset + size_bytes):
                    add_owner(byte_offset, {
                        'kind': 'patch',
                        'title': title,
                        'entry': entry_name,
                    })
            except (KeyError, TypeError, ValueError) as exc:
                warnings.append(f"patch '{title}' entry '{entry_name}': {exc}")

    return owners, warnings


def _print_xdf_diff_summary(owners: Dict[int, List[Dict]], changed_offsets, warnings: List[str]):
    """Print unique-byte attribution while retaining overlapping XDF owners."""
    changed = set(changed_offsets)
    mapped = {offset for offset in changed if owners.get(offset)}
    grouped: Dict[Tuple[str, str, Optional[str]], Dict[str, Any]] = {}
    for offset in sorted(mapped):
        for owner in owners[offset]:
            key = (owner['kind'], owner['title'], owner.get('uniqueid'))
            item = grouped.setdefault(key, {'bytes': set(), 'cells': set(), 'entries': set()})
            item['bytes'].add(offset)
            if owner.get('cell'):
                item['cells'].add(owner['cell'])
            if owner.get('entry'):
                item['entries'].add(owner['entry'])

    print(f"\nTunerPro XDF attribution: {len(mapped)}/{len(changed)} changed bytes mapped")
    print("  Counts can overlap when the XDF defines more than one item at an address.")
    if grouped:
        print(f"\n  {'TYPE':<8} {'BYTES':>7}  {'DETAIL':<16} ITEM")
        for (kind, title, _uniqueid), item in sorted(grouped.items(), key=lambda pair: (pair[0][0], pair[0][1].lower())):
            if item['cells']:
                detail = f"{len(item['cells'])} cell(s)"
            elif item['entries']:
                detail = f"{len(item['entries'])} entry(s)"
            else:
                detail = ""
            print(f"  {kind:<8} {len(item['bytes']):>7}  {detail:<16} {title}")
    unmapped = len(changed - mapped)
    if unmapped:
        print(f"  {'UNMAPPED':<8} {unmapped:>7}  {'':<16} No parsed XDF item")
    if warnings:
        print(f"\n  XDF attribution warnings ({len(warnings)}):")
        for warning in warnings[:20]:
            print(f"    ! {warning}")
        if len(warnings) > 20:
            print(f"    ... and {len(warnings) - 20} more warnings")


def cmd_diff(args):
    """Show byte-level diff, optionally attributed through a TunerPro XDF."""
    with open(args.bin_a, 'rb') as f:
        data_a = f.read()
    with open(args.bin_b, 'rb') as f:
        data_b = f.read()

    if len(data_a) != len(data_b):
        print(f"ERROR: Files differ in size ({len(data_a)} vs {len(data_b)} bytes); equal-length BINs are required.")
        return 1

    min_len = min(len(data_a), len(data_b))
    diffs = []
    for i in range(min_len):
        if data_a[i] != data_b[i]:
            diffs.append((i, data_a[i], data_b[i]))

    owners = None
    attribution_warnings = []
    if getattr(args, 'xdf', None):
        session = XDFBinSession(args.xdf, args.bin_a)
        if not session.load():
            print("ERROR: Failed to load XDF with the first BIN")
            return 1
        owners, attribution_warnings = _attribute_xdf_differences(
            session, (offset for offset, _old, _new in diffs))

    print(f"\nDiff: {args.bin_a} vs {args.bin_b}")
    print(f"Size A: {len(data_a)}, Size B: {len(data_b)}")
    print(f"Changed bytes: {len(diffs)}")

    if owners is not None:
        _print_xdf_diff_summary(
            owners, (offset for offset, _old, _new in diffs), attribution_warnings)

    if diffs:
        owner_heading = "  XDF ITEM" if owners is not None else ""
        print(f"\n{'ADDRESS':>10}  {'OLD':>5}  {'NEW':>5}  {'OLD_HEX':>8}  {'NEW_HEX':>8}{owner_heading}")
        for offset, old, new in diffs[:200]:  # Limit output
            owner_text = ""
            if owners is not None:
                labels = [_xdf_owner_label(owner) for owner in owners.get(offset, [])]
                owner_text = "  " + ("; ".join(labels) if labels else "UNMAPPED")
            print(f"0x{offset:08X}  {old:>5}  {new:>5}  0x{old:02X}      0x{new:02X}{owner_text}")
        if len(diffs) > 200:
            print(f"  ... and {len(diffs) - 200} more differences")

    return 0


def cmd_export(args):
    """Export a validated snapshot into a new, exclusively created directory."""
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1
    try:
        session.exporter._require_complete_export()
    except (EquationError, ValueError, IndexError, TypeError, KeyError) as exc:
        print(f"ERROR: Snapshot validation failed; no output created: {exc}")
        return 1

    ts = _timestamp()
    name = f"{Path(args.bin).stem}_snapshot_{ts}"
    root = Path(args.output_dir) if args.output_dir else Path(args.bin).parent / "export"
    output_dir = root / name
    try:
        # Existing directories and aliases are refused before any file opens.
        output_dir.mkdir(parents=True, exist_ok=False)
        base = output_dir / name
        results = [session.exporter.export_to_text(str(base) + ".txt"),
                   session.exporter.export_to_json(str(base) + ".json"),
                   session.exporter.export_to_markdown(str(base) + ".md")]
        if not all(results):
            print(f"ERROR: Snapshot export failed in {output_dir}; no BIN snapshot written.")
            return 1
        errors_out = str(base) + "_conversion_errors.json"
        with open(errors_out, 'x', encoding='utf-8') as f:
            json.dump({'source_bin': str(Path(args.bin)),
                       'source_xdf': str(Path(args.xdf)),
                       'omitted_count': 0, 'errors': []}, f, indent=2)
        bin_out = str(base) + ".bin"
        with open(bin_out, 'xb') as f:
            f.write(bytes(session.bin_data))
    except OSError as exc:
        print(f"ERROR: Snapshot output refused or failed: {exc}")
        return 1

    print(f"Exported to {output_dir}:")
    print(f"  BIN: {bin_out}")
    print(f"  TXT: {base}.txt")
    print(f"  JSON: {base}.json")
    print(f"  MD:  {base}.md")
    print(f"  ERR: {errors_out} (0 omitted definitions)")
    return 0


def cmd_apply_raw_patch(args):
    """Apply a strict exact-image raw patch and emit an audit receipt."""
    try:
        receipt = apply_patch_manifest(
            input_path=args.bin,
            manifest_path=args.manifest,
            output_path=args.output,
            receipt_path=args.receipt,
            reverse=args.reverse,
            checksum_verifiers=TRUSTED_CHECKSUM_VERIFIERS,
        )
    except PatchManifestError as exc:
        print(f"ERROR: {exc}")
        return 1

    proof = receipt["proof"]
    print(f"Patch: {receipt['patch_id']}")
    print(f"Direction: {receipt['direction']}")
    print(f"OSID: {receipt['output']['osid']}")
    print(f"Input SHA-256:  {receipt['input']['sha256']}")
    print(f"Output SHA-256: {receipt['output']['sha256']}")
    print(f"Changed bytes: {proof['changed_bytes']}")
    print("Expected bytes: MATCH")
    print("Outside allowlist: 0")
    print(f"Checksum: {proof['checksum_status'].upper()}")
    print(f"Evidence SHA-256: {receipt['evidence_sha256']}")
    print(f"Output: {receipt['output']['path']}")
    receipt_path = args.receipt or (str(Path(args.output).resolve()) + ".receipt.json")
    print(f"Receipt: {receipt_path}")
    return 0


def cmd_verify_raw_patch(args):
    """Verify and stage a strict raw patch without writing any file."""
    try:
        verification = verify_patch_manifest(
            input_path=args.bin,
            manifest_path=args.manifest,
            reverse=args.reverse,
            checksum_verifiers=TRUSTED_CHECKSUM_VERIFIERS,
        )
    except PatchManifestError as exc:
        print(f"ERROR: {exc}")
        return 1

    proof = verification["proof"]
    print(f"Patch: {verification['patch_id']}")
    print(f"Direction: {verification['direction']}")
    print(f"Input SHA-256:  {verification['input']['sha256']}")
    print(f"Output SHA-256: {verification['output']['sha256']}")
    print(f"Changed bytes: {proof['changed_bytes']}")
    print("Expected bytes: MATCH")
    print("Outside allowlist: 0")
    print(f"Checksum: {proof['checksum_status'].upper()}")
    print(f"Evidence SHA-256: {verification['evidence_sha256']}")
    print("Verification: PASS (no files written)")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN CLI PARSER
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(
        prog="cli_map_editor",
        description="KingAI CLI Map Editor — AI-Friendly XDF+BIN Editor v" + __version__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list-maps --xdf def.xdf --bin fw.bin
  %(prog)s show-map --xdf def.xdf --bin fw.bin --map "Fuel Map"
  %(prog)s show-flag --xdf def.xdf --bin fw.bin --name "Enable Feature"
  %(prog)s edit --xdf def.xdf --bin fw.bin --map "Fuel Map" --rows 1-3 --cols 1-2 --value 12.5 --autosave --output-dir output
  %(prog)s edit-flag --xdf def.xdf --bin fw.bin --name "Enable Feature" --state set --autosave --output-dir output
  %(prog)s preflight --xdf def.xdf --bin fw.bin
  %(prog)s diff --bin-a original.bin --bin-b edited.bin
  %(prog)s verify-raw-patch --bin fw.bin --manifest patch.json
  %(prog)s apply-raw-patch --bin fw.bin --manifest patch.json --output patched.bin
  %(prog)s apply-raw-patch --reverse --bin patched.bin --manifest patch.json --output restored.bin
"""
    )
    sp = p.add_subparsers(dest='command', required=True)

    # ─── list-maps ───────────────────────────────────────────────────────
    p_list = sp.add_parser('list-maps', help='List all maps/scalars/flags in XDF')
    p_list.add_argument('--xdf', required=True, help='XDF definition file')
    p_list.add_argument('--bin', required=True, help='BIN firmware file')
    p_list.set_defaults(func=cmd_list_maps)

    # ─── show-map ────────────────────────────────────────────────────────
    p_show = sp.add_parser('show-map', help='Show table values')
    p_show.add_argument('--xdf', required=True)
    p_show.add_argument('--bin', required=True)
    p_show.add_argument('--map', required=True, help='Table name (exact or case-insensitive)')
    p_show.set_defaults(func=cmd_show_map)

    # ─── show-scalar ─────────────────────────────────────────────────────
    p_ss = sp.add_parser('show-scalar', help='Show scalar value')
    p_ss.add_argument('--xdf', required=True)
    p_ss.add_argument('--bin', required=True)
    p_ss.add_argument('--name', required=True, help='Scalar name')
    p_ss.set_defaults(func=cmd_show_scalar)

    # ─── show-flag ───────────────────────────────────────────
    p_sf = sp.add_parser('show-flag', help='Show a bit flag state')
    p_sf.add_argument('--xdf', required=True)
    p_sf.add_argument('--bin', required=True)
    p_sf.add_argument('--name', required=True, help='Flag name')
    p_sf.set_defaults(func=cmd_show_flag)

    # ─── edit ────────────────────────────────────────────────────────────
    p_edit = sp.add_parser('edit', help='Edit table cells (single or range)')
    p_edit.add_argument('--xdf', required=True)
    p_edit.add_argument('--bin', required=True)
    p_edit.add_argument('--map', required=True, help='Table name')
    p_edit.add_argument('--rows', required=True, help="Row: '3' or range '1-5' (1-based)")
    p_edit.add_argument('--cols', required=True, help="Col: '2' or range '1-4' (1-based)")
    p_edit.add_argument('--value', required=True, type=float, help='Real-world value to set')
    p_edit.add_argument('--raw', action='store_true', help='Treat --value as raw integer')
    p_edit.add_argument('--autosave', '--save', dest='autosave', action='store_true', help='Required: save a new BIN with audit logs')
    p_edit.add_argument('--output-dir', default=None, help='Required output directory; existing files are never overwritten')
    p_edit.set_defaults(func=cmd_edit)

    # ─── edit-scalar ─────────────────────────────────────────────────────
    p_es = sp.add_parser('edit-scalar', help='Edit a scalar value')
    p_es.add_argument('--xdf', required=True)
    p_es.add_argument('--bin', required=True)
    p_es.add_argument('--name', required=True, help='Scalar name')
    p_es.add_argument('--value', required=True, type=float)
    p_es.add_argument('--raw', action='store_true')
    p_es.add_argument('--autosave', '--save', dest='autosave', action='store_true')
    p_es.add_argument('--output-dir', default=None)
    p_es.set_defaults(func=cmd_edit_scalar)

    # ─── edit-flag ───────────────────────────────────────────
    p_ef = sp.add_parser('edit-flag', help='Set or clear one bit flag')
    p_ef.add_argument('--xdf', required=True)
    p_ef.add_argument('--bin', required=True)
    p_ef.add_argument('--name', required=True, help='Flag name')
    p_ef.add_argument(
        '--state', required=True,
        help='set/clear, on/off, true/false, or 1/0',
    )
    p_ef.add_argument('--autosave', '--save', dest='autosave', action='store_true')
    p_ef.add_argument('--output-dir', default=None)
    p_ef.set_defaults(func=cmd_edit_flag)

    # ─── batch ───────────────────────────────────────────────────────────
    p_batch = sp.add_parser('batch', help='Disabled: batch transaction validation is not yet supported')
    p_batch.add_argument('--xdf', required=True)
    p_batch.add_argument('--bin', required=True)
    p_batch.add_argument(
        '--csv', required=True,
        help='CSV with columns: map,row,col,value and optional type=flag',
    )
    p_batch.add_argument('--default-map', default=None, help='Default map if CSV lacks map column')
    p_batch.add_argument('--output-dir', default=None)
    p_batch.set_defaults(func=cmd_batch)

    # ─── save ────────────────────────────────────────────────────────────
    p_save = sp.add_parser('save', help='Disabled: unbound temporary saves are not supported')
    p_save.add_argument('--bin', required=True, help='Original BIN path (expects .edited.tmp)')
    p_save.add_argument('--output-dir', default=None)
    p_save.set_defaults(func=cmd_save)

    # ─── export ──────────────────────────────────────────────────────────
    p_export = sp.add_parser('export', help='Export BIN+XDF snapshot (TXT/JSON/MD)')
    p_export.add_argument('--xdf', required=True)
    p_export.add_argument('--bin', required=True)
    p_export.add_argument('--output-dir', default=None)
    p_export.set_defaults(func=cmd_export)

    # ─── port ────────────────────────────────────────────────────────────
    p_port = sp.add_parser('port', help='Disabled: automatic map transformations are not verified')
    p_port.add_argument('--src-xdf', required=True, help='Source XDF')
    p_port.add_argument('--src-bin', required=True, help='Source BIN')
    p_port.add_argument('--dst-xdf', required=True, help='Destination XDF')
    p_port.add_argument('--dst-bin', required=True, help='Destination BIN')
    p_port.add_argument('--map-name', default=None, help='Single map name to port')
    p_port.add_argument('--map-csv', default=None, help='CSV mapping: src_name,dst_name')
    p_port.add_argument('--method', default='bilinear', choices=['bilinear', 'nearest'])
    p_port.add_argument('--stoich', type=float, default=14.7, help='Stoich AFR (default 14.7)')
    p_port.add_argument('--output-dir', default=None)
    p_port.set_defaults(func=cmd_port)

    # ─── preflight ───────────────────────────────────────────────────────
    p_pre = sp.add_parser('preflight', help='Validate XDF+BIN compatibility')
    p_pre.add_argument('--xdf', required=True)
    p_pre.add_argument('--bin', required=True)
    p_pre.set_defaults(func=cmd_preflight)

    # ─── diff ────────────────────────────────────────────────────────────
    p_diff = sp.add_parser('diff', help='Byte-level diff, optionally attributed through a TunerPro XDF')
    p_diff.add_argument('--bin-a', required=True, help='First BIN file')
    p_diff.add_argument('--bin-b', required=True, help='Second BIN file')
    p_diff.add_argument('--xdf', help='Optional TunerPro XDF used to name changed tables, scalars, flags, and patches')
    p_diff.set_defaults(func=cmd_diff)

    # ─── strict raw patch manifests ──────────────────────────────────────
    p_verify_patch = sp.add_parser(
        'verify-raw-patch',
        help='Verify and stage an exact-hash raw-byte patch without writing',
    )
    p_verify_patch.add_argument('--bin', required=True, help='Exact input BIN')
    p_verify_patch.add_argument('--manifest', required=True, help='Strict JSON patch manifest')
    p_verify_patch.add_argument(
        '--reverse',
        action='store_true',
        help='Require patched_sha256 and verify restoration of the exact base image',
    )
    p_verify_patch.set_defaults(func=cmd_verify_raw_patch)

    p_patch = sp.add_parser(
        'apply-raw-patch',
        help='Apply or reverse an exact-hash raw-byte patch manifest',
    )
    p_patch.add_argument('--bin', required=True, help='Exact input BIN')
    p_patch.add_argument('--manifest', required=True, help='Strict JSON patch manifest')
    p_patch.add_argument('--output', required=True, help='New output BIN; never overwritten')
    p_patch.add_argument(
        '--receipt',
        default=None,
        help='JSON receipt path (default: <output>.receipt.json)',
    )
    p_patch.add_argument(
        '--reverse',
        action='store_true',
        help='Require patched_sha256 and restore the exact base image',
    )
    p_patch.set_defaults(func=cmd_apply_raw_patch)

    args = p.parse_args()
    try:
        return args.func(args)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)

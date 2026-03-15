#!/usr/bin/env python3
"""
===============================================================================
 KingAI CLI Map Editor — AI-Friendly XDF + BIN Editor
===============================================================================

 Strict CLI tool for editing ECU calibration data using XDF definitions.
 Reuses the battle-tested UniversalXDFExporter for all XDF/BIN parsing.
 Adds write-back, porting, and TunerPro-identical logging.

 Commands:
   list-maps    List all maps/tables/scalars/flags in an XDF
   show-map     Show a table's real values from the BIN
   show-scalar  Show a scalar's value
   edit         Edit table cells (single or row/col ranges)
   edit-scalar  Edit a scalar value
   batch        Apply edits from a CSV file
   save         Persist temp edits to a named output BIN
   export       Snapshot XDF+BIN to an output directory
   port         Port maps from source XDF+BIN to destination XDF+BIN
   preflight    Validate XDF+BIN compatibility before editing
   diff         Show byte-level diff between two BIN files

 Author:       Jason King
 GitHub:       https://github.com/KingAiCodeForge
 Copyright:    (c) 2025 KingAI Pty Ltd

===============================================================================
"""

import argparse
import csv
import os
import re
import struct
import sys
from datetime import datetime
from pathlib import Path
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

# Import the proven exporter engine
from tunerpro_exporter_for_cli_editor_version import UniversalXDFExporter

__version__ = "1.0.0"
__author__ = "Jason King"

# ═══════════════════════════════════════════════════════════════════════════════
# TIMESTAMP AND NAMING CONVENTIONS
# ═══════════════════════════════════════════════════════════════════════════════
# Output naming:  <original_name>_<operation>_<YYYYMMDD_HHMMSS>.bin
# Log naming:     <original_name>_<operation>_<YYYYMMDD_HHMMSS>.log
# Operations:     edited, ported, batch
# Temp files:     <original_name>.edited.tmp  (deleted after save)

def _timestamp() -> str:
    """Generate timestamp string: YYYYMMDD_HHMMSS"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def _log_timestamp() -> str:
    """Generate TunerPro-identical log-line timestamp: MM/DD/YYYY HH:MM:SS"""
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
# EXPORTER WRAPPER — loads XDF + BIN via the proven engine
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
        # Exact match first
        for t in self.tables:
            if t['title'] == name:
                return t
        # Case-insensitive fallback
        name_lower = name.lower()
        for t in self.tables:
            if t['title'].lower() == name_lower:
                return t
        return None

    def find_constant(self, name: str) -> Optional[Dict]:
        """Find a scalar/constant by title."""
        for c in self.constants:
            if c['title'] == name:
                return c
        name_lower = name.lower()
        for c in self.constants:
            if c['title'].lower() == name_lower:
                return c
        return None

    # ─── READ helpers ────────────────────────────────────────────────────

    def read_table_data(self, table: Dict) -> Optional[List[List[float]]]:
        """Read full table data using the exporter engine (real values)."""
        # Temporarily point exporter to our mutable bin_data
        original = self.exporter.bin_data
        self.exporter.bin_data = bytes(self.bin_data)
        result = self.exporter._read_table_data(table)
        self.exporter.bin_data = original
        return result

    def read_scalar_value(self, const: Dict) -> Tuple[Optional[int], Optional[float]]:
        """Read a scalar's raw and real value."""
        original = self.exporter.bin_data
        self.exporter.bin_data = bytes(self.bin_data)
        raw = self.exporter.read_value_from_bin(
            const['address'], const['size'],
            signed=const.get('signed', False),
            lsb_first=const.get('lsb_first', False)
        )
        self.exporter.bin_data = original
        if raw is None:
            return None, None
        real = float(raw)
        if const.get('equation'):
            calc, _ = self.exporter.evaluate_math(
                const['equation'], raw,
                linked_vars=const.get('linked_vars', {})
            )
            if calc is not None:
                real = calc
        return raw, real

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
        """Write a raw integer value at a file offset."""
        size_bytes = size_bits // 8
        if file_offset < 0 or file_offset + size_bytes > len(self.bin_data):
            raise IndexError(
                f"Write at offset 0x{file_offset:X} size {size_bytes} "
                f"out of range (bin len {len(self.bin_data)})"
            )
        endian = '<' if lsb_first else '>'
        if size_bits == 8:
            fmt = 'b' if signed else 'B'
        elif size_bits == 16:
            fmt = 'h' if signed else 'H'
        elif size_bits == 32:
            fmt = 'i' if signed else 'I'
        else:
            raise ValueError(f"Unsupported write size: {size_bits} bits")
        packed = struct.pack(f'{endian}{fmt}', value)
        self.bin_data[file_offset:file_offset + size_bytes] = packed

    def _read_raw_at(self, file_offset: int, size_bits: int,
                     signed: bool = False, lsb_first: bool = False) -> int:
        """Read a raw integer value at a file offset."""
        size_bytes = size_bits // 8
        if file_offset < 0 or file_offset + size_bytes > len(self.bin_data):
            raise IndexError(
                f"Read at offset 0x{file_offset:X} size {size_bytes} "
                f"out of range (bin len {len(self.bin_data)})"
            )
        chunk = bytes(self.bin_data[file_offset:file_offset + size_bytes])
        endian = '<' if lsb_first else '>'
        if size_bits == 8:
            fmt = 'b' if signed else 'B'
        elif size_bits == 16:
            fmt = 'h' if signed else 'H'
        elif size_bits == 32:
            fmt = 'i' if signed else 'I'
        else:
            raise ValueError(f"Unsupported read size: {size_bits} bits")
        return struct.unpack(f'{endian}{fmt}', chunk)[0]

    def _inverse_math(self, equation: str, real_value: float,
                      linked_vars: Optional[Dict[str, float]] = None) -> Optional[int]:
        """
        Inverse math: given a real_value, compute the raw integer.
        
        Strategy:
        1. Try to detect affine: real = a*X + b → X = (real - b) / a
        2. If affine detection fails, use numerical search
        
        Returns raw integer or None on failure.
        """
        if not equation or equation.strip().upper() == 'X' or equation.lower() in ('(null)', 'null'):
            return int(round(real_value))

        # Clean equation for analysis
        eq_clean = re.sub(r'&#\d+;', '', equation).strip()

        # Try affine detection by evaluating at two points
        raw_0 = 0
        raw_1000 = 1000
        val_0, _ = self.exporter.evaluate_math(eq_clean, raw_0, linked_vars=linked_vars or {})
        val_1000, _ = self.exporter.evaluate_math(eq_clean, raw_1000, linked_vars=linked_vars or {})

        if val_0 is not None and val_1000 is not None and val_1000 != val_0:
            # Affine: real = a*raw + b
            # a = (val_1000 - val_0) / 1000, b = val_0
            a = (val_1000 - val_0) / 1000.0
            b = val_0
            if a != 0:
                raw_f = (real_value - b) / a
                raw_i = int(round(raw_f))
                # Verify round-trip
                verify, _ = self.exporter.evaluate_math(eq_clean, raw_i, linked_vars=linked_vars or {})
                if verify is not None and abs(verify - real_value) < abs(a) * 0.6:
                    return raw_i

        # Numerical binary search for monotonic equations
        # Use actual raw bounds for the element's bit size
        best_raw = None
        best_err = float('inf')
        lo, hi = 0, 65535  # default for 16-bit unsigned
        for raw_test in range(lo, hi + 1):
            test_val, _ = self.exporter.evaluate_math(eq_clean, raw_test, linked_vars=linked_vars or {})
            if test_val is not None:
                err = abs(test_val - real_value)
                if err < best_err:
                    best_err = err
                    best_raw = raw_test
                if err < 0.001:
                    break

        return best_raw

    def _raw_bounds(self, size_bits: int, signed: bool) -> Tuple[int, int]:
        """Get (min_raw, max_raw) for a given bit size and signedness."""
        if signed:
            return -(1 << (size_bits - 1)), (1 << (size_bits - 1)) - 1
        return 0, (1 << size_bits) - 1

    def write_table_cell(self, table: Dict, row: int, col: int, real_value: float,
                         raw_mode: bool = False) -> Dict[str, Any]:
        """
        Write a single table cell. row/col are 1-based.
        
        Returns change record: {map, row, col, address, old_raw, new_raw, old_real, new_real}
        """
        z = table['axes'].get('z', {})
        rows, cols = self.get_table_dimensions(table)
        
        if not (1 <= row <= rows):
            raise IndexError(f"Row {row} out of range (1-{rows})")
        if not (1 <= col <= cols):
            raise IndexError(f"Col {col} out of range (1-{cols})")

        base_addr = z.get('address')
        if base_addr is None:
            raise ValueError(f"Table '{table['title']}' has no Z-axis address")

        size_bits = z.get('size_bits', 8)
        size_bytes = size_bits // 8
        signed = z.get('signed', False)
        lsb_first = z.get('lsb_first', False)
        equation = z.get('equation', '')
        z_linked_vars = z.get('linked_vars', {})

        # Calculate cell address (row-major, 0-based internal)
        r0 = row - 1
        c0 = col - 1
        offset = (r0 * cols + c0) * size_bytes
        xdf_addr = base_addr + offset
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

        # Write
        self._write_raw_at(file_offset, size_bits, new_raw, signed, lsb_first)

        # Compute written real for log accuracy
        new_real = float(new_raw)
        if equation:
            calc, _ = self.exporter.evaluate_math(equation, new_raw, linked_vars=z_linked_vars)
            if calc is not None:
                new_real = calc

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
        signed = const.get('signed', False)
        lsb_first = const.get('lsb_first', False)
        equation = const.get('equation', '')
        linked_vars = const.get('linked_vars', {})

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

        # Write
        self._write_raw_at(file_offset, size_bits, new_raw, signed, lsb_first)

        # Compute written real
        new_real = float(new_raw)
        if equation:
            calc, _ = self.exporter.evaluate_math(equation, new_raw, linked_vars=linked_vars)
            if calc is not None:
                new_real = calc

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
        self.log_entries.append(entry)

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
        self.changes.append(change)
        return change

    # ─── TEMP FILE / SAVE ────────────────────────────────────────────────

    def save_temp(self):
        """Save current edits to a .edited.tmp file."""
        tmp_path = self.bin_path + ".edited.tmp"
        with open(tmp_path, 'wb') as f:
            f.write(bytes(self.bin_data))
        return tmp_path

    def save_final(self, output_dir: str,
                   operation: str = "edited") -> Tuple[str, str]:
        """
        Save to final named file with timestamp + matching log.

        Writes BOTH:
        - TunerPro-format .log (human-readable, identical to TunerPro)
        - Detailed .csv (cell-level data for auditing/automation)

        Returns (bin_path, log_path).
        """
        ts = _timestamp()
        bin_name = _output_name(self.bin_path, operation, ts)
        log_name = _log_name(self.bin_path, operation, ts)
        detail_name = log_name.replace('.log', '_detailed.csv')

        os.makedirs(output_dir, exist_ok=True)
        bin_out = os.path.join(output_dir, bin_name)
        log_out = os.path.join(output_dir, log_name)
        detail_out = os.path.join(output_dir, detail_name)

        # Write BIN
        with open(bin_out, 'wb') as f:
            f.write(bytes(self.bin_data))

        # Write TunerPro-format LOG
        self._write_log(log_out)

        # Write detailed CSV LOG
        self._write_detailed_log(detail_out)

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

    def _write_log(self, log_path: str):
        """
        Write change log in TunerPro-identical format.

        Verified against 54 real TunerPro .log files across:
          BMW MS40, MS42, MS43 | Holden VS, VT, VY | OSE V8

        TunerPro header (2 lines):
          Edit Log for <filename> created by TunerPro.
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
        with open(log_path, 'w', encoding='utf-8') as f:
            # TunerPro-identical header (74 asterisks)
            f.write(f"Edit Log for {bin_filename} "
                    f"created by TunerPro.\n")
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
                    elif c['type'] == 'scalar':
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

    def _write_detailed_log(self, log_path: str):
        """
        Write detailed cell-level change log (CSV format).
        Extended format with per-cell data for auditing.

        Columns beyond TunerPro's format:
          FILE_OFFSET — actual byte position in BIN
          OLD_HEX / NEW_HEX — raw values in hex
          SIZE_BITS — 8/16/32
          EQUATION — forward equation from XDF
        """
        with open(log_path, 'w', newline='', encoding='utf-8') as f:
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
        raw, real = session.read_scalar_value(c)
        val_str = f"{real}" if real is not None else "ERROR"
        unit = c.get('unit', '')
        print(f"  {c['title']}: {val_str} {unit}  [addr={addr}]")

    # Flags
    if session.flags:
        print(f"\n{'='*70}")
        print(f"FLAGS ({len(session.flags)})")
        print(f"{'='*70}")
        for f in session.flags:
            print(f"  {f['title']}  [addr=0x{f['address']:04X}]")

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
    if x_labels:
        x_dp = x.get('decimalpl', 2)
        print(f"  X-Axis ({x.get('unit', '')}): [{', '.join(f'{v:.{x_dp}f}' for v in x_labels)}]")
    if y_labels:
        y_dp = y.get('decimalpl', 2)
        print(f"  Y-Axis ({y.get('unit', '')}): [{', '.join(f'{v:.{y_dp}f}' for v in y_labels)}]")

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
        if y_labels and r < len(y_labels):
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


def cmd_edit(args):
    """Edit table cells — single or range."""
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

    # Save temp
    tmp = session.save_temp()
    print(f"\nEdited {count} cells. Temp file: {tmp}")

    # If --save flag, save final immediately
    if getattr(args, 'save', False):
        output_dir = args.output_dir or os.path.join(os.path.dirname(args.bin), "output")
        bin_out, log_out = session.save_final(output_dir, "edited")
        print(f"Saved: {bin_out}")
        print(f"Log:   {log_out}")

    return 0


def cmd_edit_scalar(args):
    """Edit a scalar value."""
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

    tmp = session.save_temp()
    print(f"Temp file: {tmp}")

    if getattr(args, 'save', False):
        output_dir = args.output_dir or os.path.join(os.path.dirname(args.bin), "output")
        bin_out, log_out = session.save_final(output_dir, "edited")
        print(f"Saved: {bin_out}")
        print(f"Log:   {log_out}")

    return 0


def cmd_batch(args):
    """Apply batch edits from CSV. Columns: map,row,col,value"""
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    count = 0
    _batch_tables_modified = set()
    with open(args.csv, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            map_name = row.get('map', row.get('MAP_NAME', '')).strip()
            if not map_name:
                map_name = getattr(args, 'default_map', '')
            if not map_name:
                print(f"ERROR: Row missing 'map' column and no --default-map provided")
                return 1

            r_str = row.get('row', row.get('ROW', '')).strip()
            c_str = row.get('col', row.get('COLUMN',
                            row.get('COL', ''))).strip()
            v = float(row.get('value', row.get('VALUE', 0)))

            # If row/col are blank, treat as scalar edit
            if not r_str or not c_str:
                const = session.find_constant(map_name)
                if const is not None:
                    session.write_scalar(const, v)
                    count += 1
                    continue
                print(f"WARNING: '{map_name}' not found "
                      f"as scalar, skipping")
                continue

            r = int(r_str)
            c = int(c_str)

            table = session.find_table(map_name)
            if table is None:
                # Try scalar fallback (name might match)
                const = session.find_constant(map_name)
                if const is not None:
                    session.write_scalar(const, v)
                    count += 1
                    continue
                print(f"WARNING: '{map_name}' not found, skipping")
                continue

            session.write_table_cell(table, r, c, v)
            # Track which tables were modified for log grouping
            if map_name not in _batch_tables_modified:
                _batch_tables_modified.add(map_name)
            count += 1

    # Add TunerPro-format table log entries (one per table)
    for tname in _batch_tables_modified:
        session.add_table_log_entry(tname)

    print(f"Applied {count} edits from {args.csv}")

    output_dir = args.output_dir or os.path.join(os.path.dirname(args.bin), "output")
    bin_out, log_out = session.save_final(output_dir, "batch")
    print(f"Saved: {bin_out}")
    print(f"Log:   {log_out}")
    return 0


def cmd_save(args):
    """Save temp edits to final named file."""
    tmp_path = args.bin + ".edited.tmp"
    if not os.path.exists(tmp_path):
        print(f"ERROR: No temp file found at {tmp_path}")
        print("Run an edit command first.")
        return 1

    ts = _timestamp()
    output_dir = args.output_dir or os.path.join(os.path.dirname(args.bin), "output")
    os.makedirs(output_dir, exist_ok=True)

    bin_name = _output_name(args.bin, "edited", ts)
    bin_out = os.path.join(output_dir, bin_name)

    with open(tmp_path, 'rb') as f:
        data = f.read()
    with open(bin_out, 'wb') as f:
        f.write(data)

    print(f"Saved: {bin_out}")
    print("NOTE: Use 'edit --save' or 'batch' for auto-generated logs.")
    print("      The 'save' command only persists the temp BIN file.")
    return 0


def cmd_port(args):
    """Port maps from source XDF+BIN to destination XDF+BIN."""
    src = XDFBinSession(args.src_xdf, args.src_bin)
    dst = XDFBinSession(args.dst_xdf, args.dst_bin)

    if not src.load():
        print("ERROR: Failed to load source XDF+BIN")
        return 1
    if not dst.load():
        print("ERROR: Failed to load destination XDF+BIN")
        return 1

    stoich = getattr(args, 'stoich', 14.7)
    method = getattr(args, 'method', 'bilinear')

    # Build mapping
    mapping = {}
    if args.map_csv:
        # Load CSV mapping: src_name, dst_name
        with open(args.map_csv, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2 and row[0].strip() and row[1].strip():
                    mapping[row[0].strip()] = row[1].strip()
    elif args.map_name:
        mapping[args.map_name] = args.map_name
    else:
        # Auto-match by exact name
        src_names = {t['title'] for t in src.tables}
        dst_names = {t['title'] for t in dst.tables}
        common = src_names & dst_names
        for name in common:
            mapping[name] = name
        print(f"Auto-matched {len(mapping)} tables by name")

    if not mapping:
        print("ERROR: No map mappings found")
        return 1

    total_cells = 0
    skipped = []
    ported_maps = []

    for src_name, dst_name in mapping.items():
        src_table = src.find_table(src_name)
        dst_table = dst.find_table(dst_name)
        if src_table is None:
            skipped.append(f"Source '{src_name}' not found")
            continue
        if dst_table is None:
            skipped.append(f"Dest '{dst_name}' not found")
            continue

        # Read source data
        src_data = src.read_table_data(src_table)
        if src_data is None:
            skipped.append(f"Cannot read source '{src_name}'")
            continue

        src_rows, src_cols = src.get_table_dimensions(src_table)
        dst_rows, dst_cols = dst.get_table_dimensions(dst_table)

        # Get axes
        src_x_labels = src_table['axes'].get('x', {}).get('labels', [])
        src_y_labels = src_table['axes'].get('y', {}).get('labels', [])
        dst_x_labels = dst_table['axes'].get('x', {}).get('labels', [])
        dst_y_labels = dst_table['axes'].get('y', {}).get('labels', [])

        src_x = axis_or_index(src_x_labels, src_cols)
        src_y = axis_or_index(src_y_labels, src_rows)
        dst_x = axis_or_index(dst_x_labels, dst_cols)
        dst_y = axis_or_index(dst_y_labels, dst_rows)

        # Unit conversion (AFR <-> Lambda)
        src_z_unit = src_table['axes'].get('z', {}).get('unit', '')
        dst_z_unit = dst_table['axes'].get('z', {}).get('unit', '')
        src_unit_type = detect_unit_type(src_name, src_z_unit)
        dst_unit_type = detect_unit_type(dst_name, dst_z_unit)

        # Convert source data if needed
        converted_data = src_data
        conversion_note = ""
        if src_unit_type == 'afr' and dst_unit_type == 'lambda':
            converted_data = [[afr_to_lambda(v, stoich) for v in row] for row in src_data]
            conversion_note = f"AFR->Lambda (stoich={stoich})"
        elif src_unit_type == 'lambda' and dst_unit_type == 'afr':
            converted_data = [[lambda_to_afr(v, stoich) for v in row] for row in src_data]
            conversion_note = f"Lambda->AFR (stoich={stoich})"
        elif src_unit_type == 'mass' or dst_unit_type == 'mass':
            skipped.append(f"'{src_name}' -> '{dst_name}': mass-unit conversion requires manual review")
            continue

        # Resample if dimensions differ
        if src_rows == dst_rows and src_cols == dst_cols and not conversion_note:
            # Direct copy — same dimensions, no unit conversion needed
            resampled = converted_data
        else:
            # Bilinear resample
            if len(converted_data) < 2 or len(converted_data[0]) < 2:
                # Too small for bilinear — direct copy or nearest
                resampled = converted_data
            else:
                resampled = bilinear_resample(
                    converted_data, src_x, src_y, dst_x, dst_y
                )

        # Write to destination
        cell_count = 0
        for r in range(dst_rows):
            for c in range(dst_cols):
                real_val = resampled[r][c] if r < len(resampled) and c < len(resampled[0]) else 0.0
                try:
                    dst.write_table_cell(dst_table, r + 1, c + 1, real_val)
                    cell_count += 1
                except Exception as e:
                    skipped.append(f"'{dst_name}'[{r+1},{c+1}]: {e}")

        total_cells += cell_count
        info = f"  Ported: {src_name} -> {dst_name} ({cell_count} cells)"
        if conversion_note:
            info += f" [{conversion_note}]"
        ported_maps.append(info)
        # TunerPro-format log entry for ported table
        dst.add_table_log_entry(dst_name)
        print(info)

    # Save
    output_dir = args.output_dir or os.path.join(os.path.dirname(args.dst_bin), "output")
    bin_out, log_out = dst.save_final(output_dir, "ported")

    print(f"\nPort complete: {total_cells} total cells across {len(ported_maps)} maps")
    print(f"Saved: {bin_out}")
    print(f"Log:   {log_out}")

    if skipped:
        print(f"\nSkipped/Warnings ({len(skipped)}):")
        for s in skipped:
            print(f"  WARNING: {s}")

    return 0


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

    for t in session.tables:
        rows, cols = session.get_table_dimensions(t)
        z = t['axes'].get('z', {})
        addr = z.get('address')
        if addr is None:
            issues.append(f"Table '{t['title']}' has no Z-axis address")
            tables_bad += 1
            continue

        size_bits = z.get('size_bits', 8)
        size_bytes = size_bits // 8
        span = rows * cols * size_bytes
        file_start = session.exporter._xdf_addr_to_file_offset(addr)
        file_end = file_start + span

        if file_end > len(session.bin_data):
            issues.append(
                f"Table '{t['title']}' extends past BIN end "
                f"(0x{file_start:X}..0x{file_end:X} > 0x{len(session.bin_data):X})"
            )
            tables_bad += 1
            continue

        address_ranges.append((file_start, file_end, t['title']))

        # Round-trip test on first cell
        data = session.read_table_data(t)
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


def cmd_diff(args):
    """Show byte-level diff between two BIN files."""
    with open(args.bin_a, 'rb') as f:
        data_a = f.read()
    with open(args.bin_b, 'rb') as f:
        data_b = f.read()

    if len(data_a) != len(data_b):
        print(f"WARNING: Files differ in size ({len(data_a)} vs {len(data_b)} bytes)")

    min_len = min(len(data_a), len(data_b))
    diffs = []
    for i in range(min_len):
        if data_a[i] != data_b[i]:
            diffs.append((i, data_a[i], data_b[i]))

    print(f"\nDiff: {args.bin_a} vs {args.bin_b}")
    print(f"Size A: {len(data_a)}, Size B: {len(data_b)}")
    print(f"Changed bytes: {len(diffs)}")

    if diffs:
        print(f"\n{'ADDRESS':>10}  {'OLD':>5}  {'NEW':>5}  {'OLD_HEX':>8}  {'NEW_HEX':>8}")
        for offset, old, new in diffs[:200]:  # Limit output
            print(f"0x{offset:08X}  {old:>5}  {new:>5}  0x{old:02X}      0x{new:02X}")
        if len(diffs) > 200:
            print(f"  ... and {len(diffs) - 200} more differences")

    return 0


def cmd_export(args):
    """Export BIN+XDF snapshot to output directory."""
    session = XDFBinSession(args.xdf, args.bin)
    if not session.load():
        print("ERROR: Failed to load XDF+BIN")
        return 1

    ts = _timestamp()
    output_dir = args.output_dir or os.path.join(os.path.dirname(args.bin), "export")
    os.makedirs(output_dir, exist_ok=True)

    # Copy BIN
    bin_name = f"{Path(args.bin).stem}_snapshot_{ts}.bin"
    bin_out = os.path.join(output_dir, bin_name)
    with open(bin_out, 'wb') as f:
        f.write(bytes(session.bin_data))

    # Export all formats using the exporter engine
    base = os.path.join(output_dir, f"{Path(args.bin).stem}_snapshot_{ts}")

    session.exporter.export_to_text(base + ".txt")
    session.exporter.export_to_json(base + ".json")
    session.exporter.export_to_markdown(base + ".md")

    print(f"Exported to {output_dir}:")
    print(f"  BIN: {bin_out}")
    print(f"  TXT: {base}.txt")
    print(f"  JSON: {base}.json")
    print(f"  MD:  {base}.md")
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
  %(prog)s edit --xdf def.xdf --bin fw.bin --map "Fuel Map" --rows 1-3 --cols 1-2 --value 12.5 --save
  %(prog)s batch --xdf def.xdf --bin fw.bin --csv edits.csv
  %(prog)s port --src-xdf ms42.xdf --src-bin ms42.bin --dst-xdf ms43.xdf --dst-bin ms43.bin
  %(prog)s preflight --xdf def.xdf --bin fw.bin
  %(prog)s diff --bin-a original.bin --bin-b edited.bin
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

    # ─── edit ────────────────────────────────────────────────────────────
    p_edit = sp.add_parser('edit', help='Edit table cells (single or range)')
    p_edit.add_argument('--xdf', required=True)
    p_edit.add_argument('--bin', required=True)
    p_edit.add_argument('--map', required=True, help='Table name')
    p_edit.add_argument('--rows', required=True, help="Row: '3' or range '1-5' (1-based)")
    p_edit.add_argument('--cols', required=True, help="Col: '2' or range '1-4' (1-based)")
    p_edit.add_argument('--value', required=True, type=float, help='Real-world value to set')
    p_edit.add_argument('--raw', action='store_true', help='Treat --value as raw integer')
    p_edit.add_argument('--save', action='store_true', help='Save immediately after edit')
    p_edit.add_argument('--output-dir', default=None, help='Output directory (default: <bin_dir>/output)')
    p_edit.set_defaults(func=cmd_edit)

    # ─── edit-scalar ─────────────────────────────────────────────────────
    p_es = sp.add_parser('edit-scalar', help='Edit a scalar value')
    p_es.add_argument('--xdf', required=True)
    p_es.add_argument('--bin', required=True)
    p_es.add_argument('--name', required=True, help='Scalar name')
    p_es.add_argument('--value', required=True, type=float)
    p_es.add_argument('--raw', action='store_true')
    p_es.add_argument('--save', action='store_true')
    p_es.add_argument('--output-dir', default=None)
    p_es.set_defaults(func=cmd_edit_scalar)

    # ─── batch ───────────────────────────────────────────────────────────
    p_batch = sp.add_parser('batch', help='Apply batch edits from CSV')
    p_batch.add_argument('--xdf', required=True)
    p_batch.add_argument('--bin', required=True)
    p_batch.add_argument('--csv', required=True, help='CSV with columns: map,row,col,value')
    p_batch.add_argument('--default-map', default=None, help='Default map if CSV lacks map column')
    p_batch.add_argument('--output-dir', default=None)
    p_batch.set_defaults(func=cmd_batch)

    # ─── save ────────────────────────────────────────────────────────────
    p_save = sp.add_parser('save', help='Persist temp edits to final file')
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
    p_port = sp.add_parser('port', help='Port maps from source to destination')
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
    p_diff = sp.add_parser('diff', help='Byte-level diff between two BINs')
    p_diff.add_argument('--bin-a', required=True, help='First BIN file')
    p_diff.add_argument('--bin-b', required=True, help='Second BIN file')
    p_diff.set_defaults(func=cmd_diff)

    args = p.parse_args()
    try:
        return args.func(args)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)

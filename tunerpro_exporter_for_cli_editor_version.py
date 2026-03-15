#!/usr/bin/env python3
"""
===============================================================================
 KingAI TunerPro XDF + BIN Universal Exporter
===============================================================================
 
 Universal XDF to Text Exporter - Enhanced Beyond TunerPro
 
 Supports ALL XDF format variations:
 - Standard format (mmedaddress, mmedelementsizebits)
 - Alternative format (mmedtypeflags)
 - Different element types (XDFCONSTANT, XDFFLAG, XDFTABLE, XDFHEADER)
 - Various structural variations (title/table/mem/desc/setups)
 
 Output Format: TunerPro-compatible PLUS enhancements
 - Clean header with SOURCE FILE and SOURCE DEFINITION
 - SCALAR: format (single line, right-aligned)
 - FLAG: format (simple "Set" or "Not Set")
 - TABLE: format with FULL DATA EXTRACTION (not just headers)
   * Complete data matrices (all cell values)
   * X-axis and Y-axis label values displayed
   * Statistical analysis (min/max/avg/unique count)
   * Zero-value detection for mismatched XDF/BIN pairs
   * Suspicious data pattern warnings
 - Optional hex addresses (--addresses flag for XDF creation)
 - Case-insensitive math evaluation
 - Comprehensive validation and error handling
 
 Enhancements over TunerPro:
 ✅ Full table data extraction (TunerPro only shows headers)
 ✅ Axis value display (TunerPro doesn't show these)
 ✅ Statistical analysis (min/max/avg for validation)
 ✅ Zero-value detection (catches XDF/BIN mismatches)
 ✅ Data integrity warnings (prevents bad tunes)
 ✅ Multiple output formats (TXT, JSON, MD, TEXT)
 needs adding - full xdf meta data and address and constants and cpu address for high and low banked binarys? maybe a v2 for this with more handling 
===============================================================================
 AUTHOR INFORMATION
===============================================================================
 
 Author:       Jason King
 GitHub:       https://github.com/KingAiCodeForge
 Email:        jason.king@kingai.com.au
 
 Project:      KingAI TunerPro Exporter
 Repository:   github.com/KingAiCodeForge/kingai_tunerpro_bin_xdf_combined_export_to_any_document
 
 Company:      KingAi PTY LTD
 Website:      kingai.com.au
 
===============================================================================
 VERSION HISTORY
===============================================================================
 
 v1.0 - Initial release with basic XDF parsing
 v2.0 - Added JSON and Markdown export formats
 v3.0 - Enhanced data extraction, validation, and statistics
 v3.1 - Added author headers, PySide6 GUI support, Windows installer
 
===============================================================================
 LICENSE
===============================================================================
 
 Copyright (c) 2025 KingAI Pty Ltd - Jason King
 
 This software is provided for educational and personal use.
 Commercial use requires written permission from the author.
 
===============================================================================
"""

import xml.etree.ElementTree as ET
import struct
import hashlib
import logging
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import re
import sys
import statistics
import json
from datetime import datetime
import io

# Fix Windows console encoding for UTF-8 characters
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def safe_print(text: str):
    """Print text safely, replacing unicode characters that can't be encoded on Windows"""
    try:
        print(text)
    except UnicodeEncodeError:
        # Replace common unicode symbols with ASCII equivalents
        replacements = {
            '✅': '[OK]',
            '❌': '[FAIL]',
            '⚠️': '[WARN]',
            '•': '*',
            '°': 'deg',
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        print(text.encode('ascii', 'replace').decode('ascii'))


__version__ = "3.5.0"  # No truncation: full titles, full descriptions, proper decimalpl everywhere, address column in MD bitshift fixes
__author__ = "Jason King"
__author_github__ = "KingAiCodeForge"
__author_alias__ = "kingaustraliagg"  # PCMHacking forum username
__email__ = "jason.king@kingai.com.au"
__copyright__ = "Copyright (c) 2025 KingAI Pty Ltd"


class UniversalXDFExporter:
    """Universal XDF parser and exporter with TunerPro-style output"""
    
    VERSION = __version__
    AUTHOR = __author__
    AUTHOR_GITHUB = __author_github__
    AUTHOR_ALIAS = __author_alias__
    
    def __init__(self, xdf_path: str, bin_path: str):
        """
        Initialize exporter with XDF definition and BIN file
        
        Args:
            xdf_path: Path to XDF definition file
            bin_path: Path to binary ECU firmware file
        """
        self.xdf_path = Path(xdf_path)
        self.bin_path = Path(bin_path)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s: %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Storage for parsed data
        self.xdf_root = None
        self.bin_data = None
        self.bin_size = 0
        self.bin_md5 = ""
        
        # XDF metadata
        self.definition_name = "Unknown"
        self.categories = {}
        self.elements = {
            'constants': [],
            'flags': [],
            'tables': [],
            'patches': []  # XDFPATCH elements (Community Patchlist support)
        }
        
        # BASEOFFSET handling for 512KB and other large bin files
        # When subtract=0: file_address = xdf_address - base_offset (offset points to where data starts in file)
        # When subtract=1: file_address = xdf_address - base_offset (same, XDF addresses are memory addresses)
        self.base_offset = 0
        self.base_subtract = 0  # 0 or 1
        
        # Index of elements by uniqueid for embedinfo axis linking (MS42/MS43 style XDFs)
        self.uniqueid_index = {}
        
        # Validation statistics
        self.validation_warnings = []
        self.suspicious_tables = []
        
        # Output options
        self.show_addresses = False  # Show hex addresses in output
        self.flip_rpm = False        # Flip Y-axis (RPM: high→low)
        self.flip_load = False       # Flip X-axis (load: high→low)
        self.no_stats = False        # Omit statistics from output
    
    def _format_value(self, value: float, decimalpl: int = 2) -> str:
        """
        Format a numeric value with correct decimal places
        
        Args:
            value: The numeric value to format
            decimalpl: Number of decimal places (from XDF)
            
        Returns:
            str: Formatted value string
        """
        if decimalpl <= 0:
            return str(int(round(value)))
        return f"{value:.{decimalpl}f}"

    def _apply_axis_flips(self, table_data, axes):
        """
        Apply --flip-rpm and --flip-load axis transforms.

        Reverses axis labels and corresponding data rows/columns
        so the presentation order changes without altering raw data.

        Args:
            table_data: 2D list of floats (rows × cols)
            axes: dict with 'x', 'y', 'z' axis info

        Returns:
            tuple: (flipped_data, flipped_axes)
        """
        import copy
        data = [list(row) for row in table_data]
        ax = copy.deepcopy(axes)

        # Flip Y-axis (RPM) → reverse row order
        if self.flip_rpm and 'y' in ax:
            data = list(reversed(data))
            if ax['y'].get('labels'):
                ax['y']['labels'] = list(
                    reversed(ax['y']['labels']))

        # Flip X-axis (load) → reverse column order
        if self.flip_load and 'x' in ax:
            data = [list(reversed(row)) for row in data]
            if ax['x'].get('labels'):
                ax['x']['labels'] = list(
                    reversed(ax['x']['labels']))

        return data, ax
        
    def validate_bin_file(self) -> bool:
        """
        Validate binary file integrity
        
        Returns:
            bool: True if valid, False otherwise
        """
        if not self.bin_path.exists():
            self.logger.error(f"Binary file not found: {self.bin_path}")
            return False
        
        # Read binary data
        try:
            with open(self.bin_path, 'rb') as f:
                self.bin_data = f.read()
                self.bin_size = len(self.bin_data)
        except Exception as e:
            self.logger.error(f"Failed to read binary: {e}")
            return False
        
        # Calculate MD5
        self.bin_md5 = hashlib.md5(self.bin_data).hexdigest()
        
        # Validate size
        common_sizes = [
            128 * 1024,  # 128KB
            256 * 1024,  # 256KB
            512 * 1024,  # 512KB
            1024 * 1024  # 1MB
        ]
        
        if self.bin_size not in common_sizes:
            self.logger.warning(
                f"Unusual binary size: {self.bin_size} bytes. "
                f"Expected: {', '.join(str(s//1024)+'KB' for s in common_sizes)}"
            )
        
        self.logger.info(
            f"Binary validated: {self.bin_size} bytes, "
            f"MD5: {self.bin_md5}"
        )
        return True
    
    def parse_xdf(self) -> bool:
        """
        Parse XDF file and extract all elements
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.xdf_path.exists():
            self.logger.error(f"XDF file not found: {self.xdf_path}")
            return False
        
        try:
            tree = ET.parse(self.xdf_path)
            self.xdf_root = tree.getroot()
        except ET.ParseError as e:
            # BUG FIX #13: Handle non-UTF-8 XDF files (e.g. German XDFs with
            # Latin-1 encoded characters like ° 0xB0, ü 0xFC, etc.)
            # Re-read as Latin-1, encode to UTF-8, then parse from string
            self.logger.warning(f"XML parse failed ({e}), retrying with Latin-1 encoding...")
            try:
                raw = self.xdf_path.read_bytes()
                # Decode as Latin-1 (ISO-8859-1) which maps all 0x00-0xFF bytes
                text = raw.decode('latin-1')
                # Strip any XML declaration that may specify wrong encoding
                text = re.sub(r'<\?xml[^?]*\?>', '<?xml version="1.0" encoding="utf-8"?>', text, count=1)
                self.xdf_root = ET.fromstring(text)
            except Exception as e2:
                self.logger.error(f"Failed to parse XDF even with Latin-1 fallback: {e2}")
                return False
        
        # Extract header information
        self._extract_header()
        
        # Extract categories
        self._extract_categories()
        
        # Build uniqueid index for embedinfo axis linking (MS42/MS43 XDFs)
        self._build_uniqueid_index()
        
        # Extract all elements (universal approach)
        self._extract_constants()
        self._extract_flags()
        self._extract_tables()
        self._extract_patches()  # XDFPATCH support for Community Patchlist
        
        self.logger.info(
            f"Parsed XDF: {len(self.elements['constants'])} constants, "
            f"{len(self.elements['flags'])} flags, "
            f"{len(self.elements['tables'])} tables, "
            f"{len(self.elements['patches'])} patches"
        )
        
        return True
    
    def _extract_header(self):
        """Extract definition name and BASEOFFSET from XDF header"""
        header = self.xdf_root.find('.//XDFHEADER')
        if header is not None:
            # Try multiple possible tags for definition name
            for tag in ['deftitle', 'title', 'name']:
                elem = header.find(tag)
                if elem is not None and elem.text:
                    self.definition_name = elem.text.strip()
                    break
            
            # Extract BASEOFFSET - critical for 512KB and full-dump bin files
            # Format 1: <BASEOFFSET offset="294912" subtract="0" />
            baseoffset = header.find('.//BASEOFFSET')
            if baseoffset is not None:
                offset_str = baseoffset.get('offset', '0')
                try:
                    self.base_offset = int(offset_str, 16) if offset_str.startswith('0x') else int(offset_str)
                except ValueError:
                    self.base_offset = 0
                
                subtract_str = baseoffset.get('subtract', '0')
                try:
                    self.base_subtract = int(subtract_str)
                except ValueError:
                    self.base_subtract = 0
                    
                if self.base_offset != 0:
                    self.logger.info(f"BASEOFFSET detected: offset={self.base_offset} (0x{self.base_offset:X}), subtract={self.base_subtract}")
            
            # Format 2: <baseoffset>0</baseoffset> (lowercase simple format)
            if self.base_offset == 0:
                baseoffset_simple = header.find('.//baseoffset')
                if baseoffset_simple is not None and baseoffset_simple.text:
                    try:
                        offset_text = baseoffset_simple.text.strip()
                        self.base_offset = int(offset_text, 16) if offset_text.startswith('0x') else int(offset_text)
                        if self.base_offset != 0:
                            self.logger.info(f"BASEOFFSET (simple format) detected: offset={self.base_offset} (0x{self.base_offset:X})")
                    except ValueError:
                        pass
    
    def _extract_categories(self):
        """Extract category definitions"""
        for cat in self.xdf_root.findall('.//CATEGORY'):
            index = cat.get('index')
            name = cat.get('name', 'Unknown')
            if index:
                # Handle hex or decimal index
                if index.startswith('0x'):
                    idx = int(index, 16)
                else:
                    idx = int(index)
                self.categories[idx] = name
    
    def _build_uniqueid_index(self):
        """
        Build index of all elements by uniqueid for embedinfo axis linking.
        
        MS42/MS43 XDFs use embedinfo to link axes to shared axis tables.
        Example: <embedinfo type="3" linkobjid="0xAA0D" />
        This links to a table with uniqueid="0xAA0D" containing axis values.
        
        This index allows O(1) lookup of linked elements.
        """
        # Index all XDFTABLE elements
        for table in self.xdf_root.findall('.//XDFTABLE'):
            uid = table.get('uniqueid')
            if uid:
                self.uniqueid_index[uid] = table
        
        # Index all XDFCONSTANT elements (scalars can be axis sources too)
        for const in self.xdf_root.findall('.//XDFCONSTANT'):
            uid = const.get('uniqueid')
            if uid:
                self.uniqueid_index[uid] = const
        
        if self.uniqueid_index:
            self.logger.info(
                f"Built uniqueid index: {len(self.uniqueid_index)} elements "
                f"(embedinfo axis linking enabled)"
            )
    
    def _resolve_linked_vars(self, math_elem) -> Dict[str, float]:
        """
        Resolve linked variable values from MATH VAR elements.
        
        TunerPro MATH blocks can contain VAR elements that link to
        other XDF elements:
          <MATH equation="X/(128/B)/C">
              <VAR id="X" />
              <VAR id="B" type="link" linkid="0xA15" />
              <VAR id="C" type="link" linkid="0x2D12" />
          </MATH>
        
        For type="link" vars, read the linked element's value from
        the binary and return it in a dict for the eval namespace.
        
        For vars without type="link" (like plain X or E), the value
        comes from context (raw_value, row_index, etc.) so they are
        not resolved here.
        
        Args:
            math_elem: MATH XML element containing VAR children
            
        Returns:
            Dict mapping variable names to resolved float values
        """
        linked_vars = {}
        if math_elem is None:
            return linked_vars
        
        for var_elem in math_elem.findall('.//VAR'):
            var_id = var_elem.get('id', '')
            var_type = var_elem.get('type', '')
            link_id = var_elem.get('linkid', '')
            
            if var_type == 'link' and link_id:
                # Resolve the linked element's value
                linked_elem = self.uniqueid_index.get(link_id)
                if linked_elem is None:
                    self.logger.debug(
                        f"Linked var {var_id} -> {link_id} "
                        f"not found in index"
                    )
                    continue
                
                # Read the linked element's value from binary
                embedded = self._parse_embedded_data(linked_elem)
                addr = embedded['address']
                if addr is not None:
                    raw = self.read_value_from_bin(
                        addr,
                        embedded['size_bits'],
                        signed=embedded['signed'],
                        lsb_first=embedded['lsb_first']
                    )
                    if raw is not None:
                        # Apply the linked element's own math if it
                        # has a simple equation (avoid recursion)
                        linked_math = linked_elem.find('.//MATH')
                        if linked_math is not None:
                            eq = linked_math.get('equation', '')
                            # Only apply simple equations (no links)
                            has_links = any(
                                v.get('type') == 'link'
                                for v in linked_math.findall('.//VAR')
                            )
                            if eq and not has_links:
                                val, _ = self.evaluate_math(
                                    eq, raw
                                )
                                if val is not None:
                                    linked_vars[var_id] = val
                                    continue
                        linked_vars[var_id] = float(raw)
        
        return linked_vars
    
    def _resolve_embedinfo_axis(self, axis_elem) -> List[float]:
        """
        Resolve axis values from embedinfo link (MS42/MS43 style).
        
        When an axis has <embedinfo type="3" linkobjid="0xXXXX" />,
        the actual axis breakpoint values come from the linked table's
        Z-axis data, read from the binary and transformed by MATH.
        
        Args:
            axis_elem: XDFAXIS element with embedinfo
            
        Returns:
            List[float]: Axis values from linked table, or empty if failed
        """
        embedinfo = axis_elem.find('.//embedinfo')
        if embedinfo is None:
            return []
        
        link_type = embedinfo.get('type')
        link_id = embedinfo.get('linkobjid')
        
        # type="3" means link to another XDF object
        if link_type != '3' or not link_id:
            return []
        
        # Find linked element by uniqueid
        linked_elem = self.uniqueid_index.get(link_id)
        if linked_elem is None:
            self.logger.warning(
                f"embedinfo link not found: {link_id}"
            )
            return []
        
        # Get Z-axis from linked table (contains actual breakpoint values)
        z_axis = linked_elem.find(".//XDFAXIS[@id='z']")
        if z_axis is None:
            # Fallback: try to get Y-axis labels from linked table
            y_axis = linked_elem.find(".//XDFAXIS[@id='y']")
            if y_axis is not None:
                return self._extract_direct_labels(y_axis)
            return []
        
        # Parse Z-axis EMBEDDEDDATA
        z_embedded = z_axis.find('.//EMBEDDEDDATA')
        if z_embedded is None:
            return []
        
        # Get address
        addr_str = z_embedded.get('mmedaddress', '0')
        try:
            address = int(addr_str, 16) if addr_str.startswith('0x') else int(addr_str)
        except ValueError:
            return []
        
        # Get size and count
        size_bits = 8  # Default
        size_str = z_embedded.get('mmedelementsizebits', '8')
        try:
            size_bits = int(size_str)
        except ValueError:
            pass
        
        row_count = 1
        row_str = z_embedded.get('mmedrowcount', '1')
        try:
            row_count = int(row_str)
        except ValueError:
            pass
        
        # Get indexcount if row_count is 1
        if row_count <= 1:
            count_elem = axis_elem.find('.//indexcount')
            if count_elem is not None and count_elem.text:
                try:
                    row_count = int(count_elem.text.strip())
                except ValueError:
                    pass
        
        # Get math equation
        z_math = z_axis.find('.//MATH')
        equation = None
        if z_math is not None:
            equation = z_math.get('equation', '')
        
        # TunerPro XDF mmedtypeflags bit definitions:
        #   Bit 0 (0x01) = Signed
        #   Bit 1 (0x02) = LSB first (little-endian)
        signed = False
        lsb_first = False
        typeflags = z_embedded.get('mmedtypeflags', '0')
        try:
            flags = int(typeflags, 16) if typeflags.startswith('0x') else int(typeflags)
            signed = (flags & 0x01) != 0      # Bit 0 = Signed
            lsb_first = (flags & 0x02) != 0   # Bit 1 = LSB first (little-endian)
        except ValueError:
            pass
        
        # Read values from binary using read_value_from_bin
        values = []
        byte_size = size_bits // 8
        if byte_size < 1:
            byte_size = 1
        
        for i in range(row_count):
            addr = address + (i * byte_size)
            raw_value = self.read_value_from_bin(
                addr, size_bits,
                signed=signed,
                lsb_first=lsb_first)
            if raw_value is None:
                break
            
            # Apply math equation
            if equation:
                final_value, _ = self.evaluate_math(equation, raw_value)
                if final_value is not None:
                    values.append(final_value)
                else:
                    values.append(float(raw_value))
            else:
                values.append(float(raw_value))
        
        return values
    
    def _extract_direct_labels(self, axis_elem) -> List[float]:
        """
        Extract LABEL values directly without embedinfo resolution.
        Helper for _resolve_embedinfo_axis fallback.
        """
        labels = []
        for label_elem in axis_elem.findall('.//LABEL'):
            value_str = label_elem.get('value', '')
            if value_str:
                try:
                    labels.append(float(value_str))
                except ValueError:
                    pass
        return labels

    def _get_address(self, element) -> Optional[int]:
        """
        Universal address extraction - handles all XDF variations
        
        Tries multiple methods:
        1. EMBEDDEDDATA mmedaddress attribute
        2. EMBEDDEDDATA mmedtypeflags with address
        3. Direct address attribute
        4. mem/memory child element
        
        Args:
            element: XML element to extract address from
            
        Returns:
            int: Address or None if not found
        """
        # Method 1: EMBEDDEDDATA with mmedaddress
        embedded = element.find('.//EMBEDDEDDATA')
        if embedded is not None:
            addr = embedded.get('mmedaddress')
            if addr:
                try:
                    return int(addr, 16) if addr.startswith('0x') else int(addr)
                except ValueError:
                    pass
            
            # Check for mmedtypeflags format
            if embedded.get('mmedtypeflags'):
                addr = embedded.get('mmedaddress')
                if addr:
                    try:
                        return int(addr, 16) if addr.startswith('0x') else int(addr)
                    except ValueError:
                        pass
        
        # Method 2: Direct address attribute
        addr = element.get('address')
        if addr:
            try:
                return int(addr, 16) if addr.startswith('0x') else int(addr)
            except ValueError:
                pass
        
        # Method 3: mem/memory child element
        for tag in ['mem', 'memory', 'addr']:
            mem = element.find(f'.//{tag}')
            if mem is not None and mem.text:
                try:
                    addr = mem.text.strip()
                    return int(addr, 16) if addr.startswith('0x') else int(addr)
                except ValueError:
                    pass
        
        return None
    
    def _parse_embedded_data(self, element) -> Dict:
        """
        Parse EMBEDDEDDATA attributes for address, size, signedness, and endianness
        
        XDF mmedtypeflags bit meanings (TunerPro spec):
        - Bit 0 (0x01): Signed value. If not set, unsigned
        - Bit 1 (0x02): LSB first (little-endian). If not set, MSB first (big-endian)
        - Other bits: Various flags (row/col major, etc.)
        
        Args:
            element: XML element containing EMBEDDEDDATA
            
        Returns:
            Dict with keys: address, size_bits, signed, lsb_first, row_count, col_count
        """
        result = {
            'address': None,
            'size_bits': 8,
            'signed': False,
            'lsb_first': False,  # False = big-endian (MSB first)
            'row_count': 1,
            'col_count': 1,
            'major_stride': 0,
            'minor_stride': 0
        }
        
        embedded = element.find('.//EMBEDDEDDATA')
        if embedded is None:
            return result
        
        # Address
        addr_str = embedded.get('mmedaddress', '')
        if addr_str:
            try:
                result['address'] = int(addr_str, 16) if addr_str.startswith('0x') else int(addr_str)
            except ValueError:
                pass
        
        # Size in bits
        size_str = embedded.get('mmedelementsizebits', '')
        if size_str:
            try:
                result['size_bits'] = int(size_str)
            except ValueError:
                pass
        
        # Type flags (signedness and endianness)
        # TunerPro XDF spec: Bit 0 = Signed, Bit 1 = LSB first (little-endian)
        # 0x00 = Unsigned MSB, 0x01 = Signed MSB, 0x02 = Unsigned LSB, 0x03 = Signed + LSB
        flags_str = embedded.get('mmedtypeflags', '0x00')
        try:
            flags = int(flags_str, 16) if flags_str.startswith('0x') else int(flags_str)
            result['signed'] = bool(flags & 0x01)      # Bit 0 = Signed
            result['lsb_first'] = bool(flags & 0x02)   # Bit 1 = LSB first (little-endian)
        except ValueError:
            pass
        
        # Row/column counts for tables
        row_str = embedded.get('mmedrowcount', '')
        if row_str:
            try:
                result['row_count'] = int(row_str)
            except ValueError:
                pass
        
        col_str = embedded.get('mmedcolcount', '')
        if col_str:
            try:
                result['col_count'] = int(col_str)
            except ValueError:
                pass
        
        # Strides for non-contiguous data
        # BUG FIX #6: Support NEGATIVE strides (BMW backwards addressing)
        major_str = embedded.get('mmedmajorstridebits', '')
        if major_str:
            try:
                result['major_stride'] = int(major_str)  # Can be negative!
            except ValueError:
                pass
        
        minor_str = embedded.get('mmedminorstridebits', '')
        if minor_str:
            try:
                result['minor_stride'] = int(minor_str)
            except ValueError:
                pass
        
        return result
    
    def _get_element_size(self, element) -> int:
        """
        Get element size in bits (legacy method, kept for compatibility)
        
        Args:
            element: XML element
            
        Returns:
            int: Size in bits (default 8)
        """
        embedded_data = self._parse_embedded_data(element)
        return embedded_data['size_bits']
    
    def _xdf_addr_to_file_offset(self, xdf_address: int) -> int:
        """
        Convert XDF memory address to actual file offset
        
        XDF files can specify a BASEOFFSET in the header which indicates where
        the ECU memory space maps to in the file.
        
        BASEOFFSET semantics in TunerPro:
        - subtract="0" (default): file_offset = xdf_address + offset
          (BIN file has header/padding before calibration data)
          e.g., XDF addr 0x0000 with offset 0x48000 → file offset 0x48000
          
        - subtract="1": file_offset = xdf_address - offset  
          (ECU memory starts at offset, but BIN starts at 0)
          e.g., XDF addr 0x8000 with offset 0x8000, subtract=1 → file offset 0x0000
          Common for 68HC11-based ECUs (VN-VY Holden, Ford AU)
        
        Args:
            xdf_address: Address from XDF element (mmedaddress)
            
        Returns:
            int: Actual file offset to read from
        """
        if self.base_offset == 0:
            return xdf_address
        
        # XDF addresses are ECU memory addresses
        # BASEOFFSET + subtract flag determines translation
        if self.base_subtract == 1:
            # subtract=1: ECU addresses start at offset, file starts at 0
            file_offset = xdf_address - self.base_offset
        else:
            # subtract=0: File has padding/header before calibration
            file_offset = xdf_address + self.base_offset
        
        # Sanity check - file offset should be non-negative
        if file_offset < 0:
            self.logger.warning(
                f"Calculated negative file offset: XDF addr 0x{xdf_address:X} "
                f"{'- ' if self.base_subtract else '+ '}{self.base_offset} = {file_offset}. "
                f"Using raw address."
            )
            return xdf_address  # Fall back to raw address
        
        return file_offset
    
    def _get_title(self, element) -> str:
        """
        Universal title extraction
        
        Args:
            element: XML element
            
        Returns:
            str: Title or "Unknown"
        """
        # Try multiple possible tags
        for tag in ['title', 'name', 'label', 'desc']:
            elem = element.find(f'.//{tag}')
            if elem is not None and elem.text:
                return elem.text.strip()
        
        return "Unknown"
    
    def _get_category_name(self, element) -> str:
        """
        Get category name for element
        
        Args:
            element: XML element
            
        Returns:
            str: Category name
        """
        cat_mem = element.find('.//CATEGORYMEM')
        if cat_mem is not None:
            cat_idx = cat_mem.get('category')
            if cat_idx:
                try:
                    idx = int(cat_idx, 16) if cat_idx.startswith('0x') else int(cat_idx)
                    return self.categories.get(idx, 'Unknown')
                except ValueError:
                    pass
        return 'Uncategorized'
    
    def _extract_constants(self):
        """Extract all constants (SCALAR values) with bug fixes"""
        for const in self.xdf_root.findall('.//XDFCONSTANT'):
            # Parse embedded data for full info
            embedded = self._parse_embedded_data(const)
            address = embedded['address']
            
            # BUG FIX #5: Validate address exists before processing
            if address is None:
                title = self._get_title(const)
                self.logger.warning(f"Constant '{title}' has no address, skipping")
                continue
            
            title = self._get_title(const)
            category = self._get_category_name(const)
            
            # Get unit
            unit_elem = const.find('.//units')
            unit = unit_elem.text.strip() if unit_elem is not None and unit_elem.text else ""
            
            # Get math equation
            math_elem = const.find('.//MATH')
            equation = None
            linked_vars = {}
            if math_elem is not None:
                equation = math_elem.get('equation', '')
                linked_vars = self._resolve_linked_vars(math_elem)
            
            # Get decimal places for precision (BUG FIX #9)
            decimalpl = 2  # Default
            dec_elem = const.find('.//decimalpl')
            if dec_elem is not None and dec_elem.text:
                try:
                    decimalpl = int(dec_elem.text.strip())
                except ValueError:
                    pass
            
            # BUG FIX #8: Extract range validation metadata
            min_val = None
            max_val = None
            rangelow_elem = const.find('.//rangelow')
            rangehigh_elem = const.find('.//rangehigh')
            
            if rangelow_elem is not None and rangelow_elem.text:
                try:
                    min_val = float(rangelow_elem.text.strip())
                except ValueError:
                    pass
            if rangehigh_elem is not None and rangehigh_elem.text:
                try:
                    max_val = float(rangehigh_elem.text.strip())
                except ValueError:
                    pass
            
            # Legacy min/max tags (fallback)
            if min_val is None:
                min_elem = const.find('.//min')
                if min_elem is not None and min_elem.text:
                    try:
                        min_val = float(min_elem.text.strip())
                    except ValueError:
                        pass
            if max_val is None:
                max_elem = const.find('.//max')
                if max_elem is not None and max_elem.text:
                    try:
                        max_val = float(max_elem.text.strip())
                    except ValueError:
                        pass
            
            self.elements['constants'].append({
                'title': title,
                'address': address,
                'size': embedded['size_bits'],
                'signed': embedded['signed'],
                'lsb_first': embedded['lsb_first'],
                'unit': unit,
                'equation': equation,
                'linked_vars': linked_vars,
                'category': category,
                'decimalpl': decimalpl,
                'min': min_val,
                'max': max_val
            })
    
    def _extract_flags(self):
        """Extract all flags (bit flags)"""
        for flag in self.xdf_root.findall('.//XDFFLAG'):
            address = self._get_address(flag)
            if address is None:
                continue
            
            title = self._get_title(flag)
            category = self._get_category_name(flag)
            
            # Get mask
            mask_elem = flag.find('.//mask')
            mask = 0x01  # Default mask
            if mask_elem is not None and mask_elem.text:
                try:
                    mask_str = mask_elem.text.strip()
                    mask = int(mask_str, 16) if mask_str.startswith('0x') else int(mask_str)
                except ValueError:
                    pass
            
            self.elements['flags'].append({
                'title': title,
                'address': address,
                'mask': mask,
                'category': category
            })
    
    def _extract_axis_labels(self, axis_elem) -> List[float]:
        """
        Extract and process axis label values.
        
        Supports two methods:
        1. embedinfo linking (MS42/MS43 style) - axis values from linked table
        2. Direct LABEL values (VY V6/legacy style) - hardcoded in XDF
        
        Args:
            axis_elem: XDF XDFAXIS element
            
        Returns:
            List[float]: Processed label values
        """
        # Method 1: Check for embedinfo linking first (MS42/MS43 XDFs)
        embedinfo = axis_elem.find('.//embedinfo')
        if embedinfo is not None:
            link_type = embedinfo.get('type')
            if link_type == '3':
                linked_values = self._resolve_embedinfo_axis(axis_elem)
                if linked_values:
                    return linked_values
        
        # Method 2: Direct LABEL extraction (VY V6/legacy XDFs)
        labels = []
        
        # Get math equation for labels
        math_elem = axis_elem.find('.//MATH')
        equation = None
        label_linked_vars = {}
        if math_elem is not None:
            equation = math_elem.get('equation', '')
            label_linked_vars = self._resolve_linked_vars(
                math_elem
            )
        
        # Extract all label values
        for label_elem in axis_elem.findall('.//LABEL'):
            value_str = label_elem.get('value', '')
            if not value_str:
                continue
            
            try:
                # Parse raw value
                raw_value = float(value_str)
                
                # Apply math equation if present
                if equation:
                    final_value, error = self.evaluate_math(
                        equation, raw_value,
                        linked_vars=label_linked_vars
                    )
                    if final_value is not None:
                        labels.append(final_value)
                    else:
                        labels.append(raw_value)
                else:
                    labels.append(raw_value)
                    
            except ValueError:
                continue
        
        return labels
    
    def _extract_tables(self):
        """Extract all tables (2D/3D lookup tables)"""
        for table in self.xdf_root.findall('.//XDFTABLE'):
            title = self._get_title(table)
            category = self._get_category_name(table)
            
            # Get decimal places for precision
            decimalpl = 2  # Default
            dec_elem = table.find('.//decimalpl')
            if dec_elem is not None and dec_elem.text:
                try:
                    decimalpl = int(dec_elem.text.strip())
                except ValueError:
                    pass
            
            # Extract axes information
            axes = {}
            for axis in table.findall('.//XDFAXIS'):
                axis_id = axis.get('id', 'unknown')
                
                # Parse EMBEDDEDDATA for full info
                embedded = self._parse_embedded_data(axis)
                
                # Get axis size/count from indexcount element
                count_elem = axis.find('.//indexcount')
                count = 1
                if count_elem is not None and count_elem.text:
                    try:
                        count = int(count_elem.text.strip())
                    except ValueError:
                        pass
                
                # For Z-axis, also check row/col counts from EMBEDDEDDATA
                if axis_id == 'z':
                    if embedded['row_count'] > 1:
                        count = embedded['row_count'] * embedded['col_count']
                
                # Get axis unit
                unit_elem = axis.find('.//units')
                unit = ""
                if unit_elem is not None and unit_elem.text:
                    unit = unit_elem.text.strip()
                
                # Get math equation and linked vars
                math_elem = axis.find('.//MATH')
                equation = None
                axis_linked_vars = {}
                if math_elem is not None:
                    equation = math_elem.get('equation', '')
                    axis_linked_vars = self._resolve_linked_vars(
                        math_elem
                    )
                
                # Get axis-specific decimal places
                axis_decimalpl = decimalpl  # Default to table's decimalpl
                axis_dec_elem = axis.find('.//decimalpl')
                if axis_dec_elem is not None and axis_dec_elem.text:
                    try:
                        axis_decimalpl = int(axis_dec_elem.text.strip())
                    except ValueError:
                        pass
                
                # Extract axis labels with processing
                axis_labels = self._extract_axis_labels(axis)
                
                axes[axis_id] = {
                    'address': embedded['address'],
                    'count': count,
                    'unit': unit,
                    'equation': equation,
                    'linked_vars': axis_linked_vars,
                    'labels': axis_labels,
                    'size_bits': embedded['size_bits'],
                    'signed': embedded['signed'],
                    'lsb_first': embedded['lsb_first'],
                    'row_count': embedded['row_count'],
                    'col_count': embedded['col_count'],
                    'decimalpl': axis_decimalpl
                }
            
            # Get Z-axis (data) information
            z_axis = axes.get('z', {})
            data_address = z_axis.get('address')
            
            if data_address is not None:
                self.elements['tables'].append({
                    'title': title,
                    'category': category,
                    'axes': axes,
                    'decimalpl': decimalpl
                })
    
    def _extract_patches(self):
        """
        Extract all XDFPATCH elements (Community Patchlist support)
        
        XDFPATCH elements define binary patches that can be applied/unapplied.
        Each patch has:
        - title: Patch name (e.g., "[PATCH] Alpha/N")
        - description: What the patch does
        - XDFPATCHENTRY elements with address, patchdata, and basedata
        
        This checks the BIN to determine if each patch is applied or not.
        """
        for patch in self.xdf_root.findall('.//XDFPATCH'):
            title = self._get_title(patch)
            category = self._get_category_name(patch)
            
            # Get description
            desc_elem = patch.find('.//description')
            description = ""
            if desc_elem is not None and desc_elem.text:
                description = desc_elem.text.strip()
                # Clean up XML entities
                description = description.replace('&#013;&#010;', '\n')
                description = description.replace('&#013;', '\r')
                description = description.replace('&#010;', '\n')
            
            # Extract all patch entries
            entries = []
            for entry in patch.findall('.//XDFPATCHENTRY'):
                entry_name = entry.get('name', 'Unknown')
                addr_str = entry.get('address', '0')
                size_str = entry.get('datasize', '0')
                patch_data = entry.get('patchdata', '')
                base_data = entry.get('basedata', '')
                
                try:
                    # Parse address and size
                    address = int(addr_str, 16) if addr_str.startswith('0x') else int(addr_str)
                    datasize = int(size_str, 16) if size_str.startswith('0x') else int(size_str)
                    
                    entries.append({
                        'name': entry_name,
                        'address': address,
                        'datasize': datasize,
                        'patchdata': patch_data.upper(),
                        'basedata': base_data.upper()
                    })
                except ValueError:
                    continue
            
            if entries:
                # Check if patch is applied
                patch_status = self._check_patch_status(entries)
                
                self.elements['patches'].append({
                    'title': title,
                    'description': description,
                    'category': category,
                    'entries': entries,
                    'status': patch_status
                })
    
    def _check_patch_status(self, entries: List[Dict]) -> str:
        """
        Check if a patch is applied, not applied, or partially applied
        
        Args:
            entries: List of XDFPATCHENTRY dictionaries
            
        Returns:
            str: 'applied', 'not_applied', 'partial', or 'unknown'
        """
        if not entries or self.bin_data is None:
            return 'unknown'
        
        applied_count = 0
        base_count = 0
        total = len(entries)
        
        for entry in entries:
            address = entry['address']
            datasize = entry['datasize']
            patch_data = entry['patchdata']
            base_data = entry['basedata']
            
            # Convert address to file offset
            file_offset = self._xdf_addr_to_file_offset(address)
            
            # Validate offset
            if file_offset < 0 or file_offset + datasize > self.bin_size:
                continue
            
            # Read actual bytes from BIN
            actual_bytes = self.bin_data[file_offset:file_offset + datasize]
            actual_hex = actual_bytes.hex().upper()
            
            # Check if matches patch or base data
            if patch_data and actual_hex == patch_data:
                applied_count += 1
            elif base_data and actual_hex == base_data:
                base_count += 1
        
        # Determine status
        if applied_count == total:
            return 'applied'
        elif base_count == total:
            return 'not_applied'
        elif applied_count > 0 and base_count > 0:
            return 'partial'
        elif applied_count > 0:
            return 'applied'
        elif base_count > 0:
            return 'not_applied'
        else:
            return 'unknown'

    def read_value_from_bin(self, address: int, size_bits: int, 
                           signed: bool = False,
                           lsb_first: bool = False) -> Optional[int]:
        """
        Read value from binary file with validation
        
        Args:
            address: XDF memory address (will be converted to file offset)
            size_bits: Size in bits (8, 16, 32)
            signed: Whether value is signed
            lsb_first: True for little-endian, False for big-endian
            
        Returns:
            int: Value or None if error
        """
        # Convert XDF address to actual file offset
        file_offset = self._xdf_addr_to_file_offset(address)
        
        if not 0 <= file_offset < self.bin_size:
            self.logger.warning(
                f"Address 0x{address:04X} -> file offset 0x{file_offset:04X} out of range "
                f"(0x0000-0x{self.bin_size-1:04X})"
            )
            return None
        
        size_bytes = size_bits // 8
        
        if file_offset + size_bytes > self.bin_size:
            self.logger.warning(
                f"Read at 0x{file_offset:04X} extends beyond binary end"
            )
            return None
        
        try:
            data = self.bin_data[file_offset:file_offset + size_bytes]
            
            # Determine endianness prefix: < for little-endian, > for big-endian
            endian = '<' if lsb_first else '>'
            
            # Unpack based on size and signedness
            if size_bits == 8:
                fmt = 'b' if signed else 'B'
                value = struct.unpack(f'{endian}{fmt}', data)[0]
            elif size_bits == 16:
                fmt = 'h' if signed else 'H'
                value = struct.unpack(f'{endian}{fmt}', data)[0]
            elif size_bits == 32:
                fmt = 'i' if signed else 'I'
                value = struct.unpack(f'{endian}{fmt}', data)[0]
            else:
                self.logger.warning(f"Unsupported size: {size_bits} bits")
                return None
            
            return value
            
        except struct.error as e:
            self.logger.warning(
                f"Failed to unpack value at 0x{address:04X}: {e}"
            )
            return None
    
    def _read_table_data(self, table: Dict) -> Optional[List[List[float]]]:
        """Read full 2D/3D table data from binary with NEGATIVE STRIDE support (BUG FIX #6)"""
        z_axis = table['axes'].get('z', {})
        y_axis = table['axes'].get('y', {})
        x_axis = table['axes'].get('x', {})
        
        # Get dimensions - prefer row_count/col_count from EMBEDDEDDATA
        rows = z_axis.get('row_count', 1)
        cols = z_axis.get('col_count', 1)
        
        # Fallback to axis counts if EMBEDDEDDATA didn't have row/col
        if rows <= 1 and cols <= 1:
            y_count = y_axis.get('count', 1)
            x_count = x_axis.get('count', 1)
            rows = max(y_count, 1)
            cols = max(x_count, 1)
        
        # For 1D tables (scalars with multiple values)
        if rows <= 1 and cols <= 1:
            return None
        
        # Get base address from Z-axis (data values)
        base_address = z_axis.get('address')
        if base_address is None:
            return None
        
        size_bits = z_axis.get('size_bits', 8)
        size_bytes = size_bits // 8
        math_eq = z_axis.get('equation', '')
        z_linked_vars = z_axis.get('linked_vars', {})
        signed = z_axis.get('signed', False)
        lsb_first = z_axis.get('lsb_first', False)
        
        # BUG FIX #6: Get strides (can be NEGATIVE for BMW!)
        major_stride = z_axis.get('major_stride', size_bits)
        minor_stride = z_axis.get('minor_stride', size_bits)
        
        # Convert bit strides to bytes
        if major_stride == 0:
            major_stride = size_bits
        if minor_stride == 0:
            minor_stride = size_bits
        
        major_stride_bytes = major_stride // 8
        minor_stride_bytes = minor_stride // 8
        
        # Handle NEGATIVE stride (backwards addressing for BMW XDFs)
        if major_stride < 0:
            # Start at the END of the data block for backwards addressing
            start_address = base_address + (rows - 1) * abs(major_stride_bytes) * cols
            major_stride_bytes = -abs(major_stride_bytes)  # Keep negative for decrement
            self.logger.info(f"Table '{table['title']}' uses NEGATIVE stride (BMW backwards addressing)")
        else:
            start_address = base_address
        
        # Read table data
        data = []
        
        for row in range(rows):
            row_data = []
            for col in range(cols):
                # BUG FIX #6: Calculate offset with support for negative stride
                if major_stride < 0:
                    offset = start_address - (row * abs(major_stride_bytes) * cols) + (col * minor_stride_bytes)
                else:
                    offset = (row * cols + col) * size_bytes
                    address = base_address + offset
                
                if major_stride < 0:
                    address = offset
                
                # Convert to file offset for bounds checking
                file_offset = self._xdf_addr_to_file_offset(address)
                
                # Validate file offset (not the raw XDF address)
                if file_offset + size_bytes > self.bin_size:
                    self.logger.warning(
                        f"Table '{table['title']}' file offset 0x{file_offset:04X} "
                        f"(from XDF addr 0x{address:04X}) out of bounds"
                    )
                    return None
                
                # Read raw value with proper signed/endian settings
                raw_value = self.read_value_from_bin(
                    address, size_bits, signed=signed, lsb_first=lsb_first
                )
                if raw_value is None:
                    row_data.append(0.0)
                    continue
                
                # BUG FIX #7: Apply math equation with axis context for multi-variable support
                if math_eq:
                    axis_context = {
                        'row_index': row,
                        'col_index': col,
                        'y_axis_value': y_axis.get('labels', [])[row] if row < len(y_axis.get('labels', [])) else 0,
                        'x_axis_value': x_axis.get('labels', [])[col] if col < len(x_axis.get('labels', [])) else 0
                    }
                    final_value, _ = self.evaluate_math(
                        math_eq, raw_value, axis_context,
                        linked_vars=z_linked_vars
                    )
                    if final_value is not None:
                        row_data.append(final_value)
                    else:
                        row_data.append(float(raw_value))
                else:
                    row_data.append(float(raw_value))
            
            data.append(row_data)
        
        return data
    
    def _validate_table_data(self, table: Dict, data: List[List[float]]) -> Dict[str, Any]:
        """Validate table data for suspicious patterns"""
        if not data or not data[0]:
            return {'valid': True, 'warnings': []}
        
        # Flatten data for analysis
        flat_data = [cell for row in data for cell in row]
        
        # Check for all zeros
        all_zeros = all(cell == 0.0 for cell in flat_data)
        
        # Check for all same value
        unique_values = set(flat_data)
        all_same = len(unique_values) == 1
        
        # Check for suspicious patterns
        warnings = []
        
        if all_zeros:
            warnings.append("All cells are zero - possible XDF/BIN mismatch")
        elif all_same and len(flat_data) > 4:  # Allow small tables with same value
            warnings.append(f"All cells have same value ({flat_data[0]}) - verify data integrity")
        
        # Calculate statistics
        stats = {
            'min': min(flat_data),
            'max': max(flat_data),
            'avg': statistics.mean(flat_data),
            'unique_count': len(unique_values)
        }
        
        return {
            'valid': not all_zeros,
            'warnings': warnings,
            'all_zeros': all_zeros,
            'all_same': all_same,
            'stats': stats
        }
    
    def evaluate_math(self, equation: str, raw_value: int,
                       axis_context: Optional[Dict] = None,
                       linked_vars: Optional[Dict[str, float]] = None
                       ) -> Tuple[Optional[float], str]:
        """
        Evaluate math equation with comprehensive variable and function support
        
        FIXED BUGS:
        - #1: Division by zero protection (check for inf/nan)
        - #2: XML entity stripping (&#013;&#010; etc)
        - #3: Exponential/math functions (exp, log, sqrt, pow)
        - #4: Null equation handling ((null), null, empty)
        - #7: Multi-variable support (A, B, Y, E, Z for tables)
        - #11: Linked variable resolution (VAR type="link")
        
        Args:
            equation: Math equation string (e.g., "0.75 * X - 40")
            raw_value: Raw binary value
            axis_context: Optional dict with 'row_index', 'col_index',
                         'x_axis_value', 'y_axis_value'
            linked_vars: Optional dict of resolved linked variable values
                        from _resolve_linked_vars()
            
        Returns:
            Tuple[Optional[float], str]: (result, error_message)
        """
        if axis_context is None:
            axis_context = {}
        
        # BUG FIX #2: Strip XML entities (&#013;&#010; = CRLF, etc)
        equation = re.sub(r'&#\d+;', '', equation)
        equation = equation.strip()
        
        # BUG FIX #4: Handle null/empty equations
        if not equation or equation.lower() in ('(null)', 'null', ''):
            return float(raw_value), ""
        
        # Handle simple X passthrough
        if equation.strip().upper() == 'X':
            return float(raw_value), ""
        
        # BUG FIX #1: Pre-check for potential division by zero
        if raw_value == 0 and re.search(r'/\s*[xX]\b', equation):
            self.logger.warning(f"Potential division by zero in equation: {equation} (X=0)")
            # Continue anyway, let exception handler catch actual errors
        
        try:
            equation_fixed = equation.strip()
            
            # Fix equations starting with * or / operator (e.g., "*2**14" -> "X*2**14")
            # BUG FIX #12: Do NOT prepend X for leading - or + (unary sign/coefficient)
            # e.g., "-0.375*X-60.0" is a valid equation with negative coefficient
            if equation_fixed.startswith(('*', '/')):
                equation_fixed = 'X' + equation_fixed
            
            # Replace named variables like X1000, X100, X10 with the raw value
            equation_fixed = re.sub(r'\bX\d+\b', str(raw_value), equation_fixed, flags=re.IGNORECASE)
            
            # BUG FIX #8: Convert TunerPro if(cond ; true ; false) ternary to Python
            # TunerPro uses: if ( condition ; value_if_true ; value_if_false )
            # Python needs:  (value_if_true) if (condition) else (value_if_false)
            tp_if_match = re.match(
                r'^\s*if\s*\(\s*(.+?)\s*;\s*(.+?)\s*;\s*(.+?)\s*\)\s*$',
                equation_fixed, re.IGNORECASE
            )
            if tp_if_match:
                cond_part = tp_if_match.group(1).strip()
                true_part = tp_if_match.group(2).strip()
                false_part = tp_if_match.group(3).strip()
                equation_fixed = f"({true_part}) if ({cond_part}) else ({false_part})"
            
            # BUG FIX #9: Ensure bitshift operands are integers
            # Python's >> and << require int operands, but XDF axis values
            # may be floats. Wrap variable references in int() where >> or << appear.
            if '>>' in equation_fixed or '<<' in equation_fixed:
                equation_fixed = re.sub(r'\bY\b', 'int(Y)', equation_fixed)
                equation_fixed = re.sub(r'\bX\b', 'int(X)', equation_fixed)
                equation_fixed = re.sub(r'\bA\b', 'int(A)', equation_fixed)
                equation_fixed = re.sub(r'\bB\b', 'int(B)', equation_fixed)
                # Clean up double-wrapping: int(int(X)) -> int(X)
                equation_fixed = re.sub(r'int\(int\(', 'int(', equation_fixed)
            
            # BUG FIX #3 & #7: Create comprehensive evaluation namespace
            # Default E to 1 (not 0) — for scalars E=element count=1
            # This prevents div-by-zero in formulas like X/2.56/E
            namespace = {
                # Primary data value
                'X': raw_value,
                'x': raw_value,
                
                # Multi-variable support (for tables with axis context)
                'A': axis_context.get('row_index', 0),
                'a': axis_context.get('row_index', 0),
                'B': axis_context.get('col_index', 1),
                'b': axis_context.get('col_index', 1),
                'C': axis_context.get('c_value', 1),
                'c': axis_context.get('c_value', 1),
                'E': axis_context.get('row_index', 1),
                'e': axis_context.get('row_index', 1),
                'Y': axis_context.get('y_axis_value', 0),
                'y': axis_context.get('y_axis_value', 0),
                'Z': axis_context.get('x_axis_value', 0),
                'z': axis_context.get('x_axis_value', 0),
                
                # Math functions (for exponential equations)
                'exp': math.exp,
                'log': math.log,
                'log10': math.log10,
                'sqrt': math.sqrt,
                'pow': math.pow,
                'abs': abs,
                'int': int,
                'float': float,
                'sin': math.sin,
                'cos': math.cos,
                'tan': math.tan,
                
                # Mathematical constants
                # BUG FIX #10: Don't overwrite 'E' row_index with math.e
                # Use 'euler_e' or only set 'E' to math.e if not used as axis
                'PI': math.pi,
                'pi': math.pi,
                
                '__builtins__': {}
            }
            
            # BUG FIX #11: Apply linked variable overrides
            # Linked vars (from VAR type="link") take priority
            # over default axis context values
            if linked_vars:
                for var_name, var_val in linked_vars.items():
                    namespace[var_name] = var_val
                    namespace[var_name.lower()] = var_val
            
            # Evaluate the expression
            result = eval(equation_fixed, namespace)
            
            # BUG FIX #1: Check for invalid results (inf/nan from division by zero)
            if math.isinf(result):
                self.logger.warning(f"Equation resulted in infinity: {equation} (X={raw_value})")
                return None, f"Division by zero (result=inf)"
            if math.isnan(result):
                self.logger.warning(f"Equation resulted in NaN: {equation} (X={raw_value})")
                return None, f"Invalid math operation (result=NaN)"
            
            return float(result), ""
            
        except ZeroDivisionError:
            self.logger.warning(f"Division by zero in equation: {equation} (X={raw_value})")
            return None, f"Division by zero"
        except Exception as e:
            self.logger.error(f"Math evaluation failed for '{equation}' with X={raw_value}: {str(e)}")
            return None, f"Math evaluation failed: {str(e)}"
    
    def export_to_text(self, output_path: str) -> bool:
        """
        Export data in TunerPro format with enhancements
        
        Args:
            output_path: Output file path
            
        Returns:
            bool: True if successful
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write TunerPro-style header
                f.write("=" * 60 + "\n")
                f.write("TunerPro Bin Data Export\n")
                f.write("=" * 60 + "\n")
                f.write(f"SOURCE FILE: {self.bin_path.name}\n")
                f.write(f"SOURCE DEFINITION: {self.definition_name}\n")
                f.write(f"Binary Size: {self.bin_size} bytes\n")
                f.write(f"MD5 Checksum: {self.bin_md5}\n")
                f.write(f"Exporter: KingAI TunerPro Exporter v{self.VERSION}\n")
                f.write(f"Author: {self.AUTHOR_ALIAS} ({self.AUTHOR})\n")
                f.write("=" * 60 + "\n\n")
                
                # Export SCALARS (constants)
                if self.elements['constants']:
                    f.write("=" * 60 + "\n")
                    f.write("SCALAR VALUES\n")
                    f.write("=" * 60 + "\n\n")
                    
                    for const in self.elements['constants']:
                        raw_value = self.read_value_from_bin(
                            const['address'],
                            const['size'],
                            signed=const.get('signed', False),
                            lsb_first=const.get('lsb_first', False)
                        )
                        
                        if raw_value is None:
                            continue
                        
                        # Apply math equation
                        value = raw_value
                        if const['equation']:
                            calc_value, error = self.evaluate_math(
                                const['equation'],
                                raw_value,
                                linked_vars=const.get(
                                    'linked_vars', {}
                                )
                            )
                            if calc_value is not None:
                                value = calc_value
                            elif error:
                                self.logger.warning(
                                    f"{const['title']}: {error}"
                                )
                        
                        # Format value with unit using stored decimal places
                        decimalpl = const.get('decimalpl', 2)
                        if isinstance(value, float):
                            value_str = f"{value:.{decimalpl}f}"
                        else:
                            value_str = str(value)
                        
                        # Add unit if present
                        if const['unit']:
                            value_str += f" {const['unit']}"
                        
                        # Write in TunerPro format: single line, right-aligned
                        title = const['title']  # Full title, no truncation
                        if self.show_addresses and const['address'] is not None:
                            addr_str = f"[0x{const['address']:04X}]"
                            f.write(f"SCALAR: {addr_str} {title:<60} {value_str:>18}\n")
                        else:
                            f.write(f"SCALAR: {title:<60} {value_str:>22}\n")
                
                # Export FLAGS
                if self.elements['flags']:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("FLAG VALUES\n")
                    f.write("=" * 60 + "\n\n")
                    
                    for flag in self.elements['flags']:
                        byte_value = self.read_value_from_bin(
                            flag['address'],
                            8
                        )
                        
                        if byte_value is None:
                            continue
                        
                        # Check if flag is set
                        is_set = (byte_value & flag['mask']) != 0
                        status = "Set" if is_set else "Not Set"
                        
                        # Write in TunerPro format: simple Set/Not Set
                        if self.show_addresses and flag['address'] is not None:
                            addr_str = f"[0x{flag['address']:04X}]"
                            mask_str = f"mask=0x{flag['mask']:02X}"
                            f.write(f"FLAG: {addr_str} {mask_str} {flag['title']:<40} {status:>10}\n")
                        else:
                            f.write(f"FLAG: {flag['title']:<50} {status:>20}\n")
                
                # Export TABLES with FULL DATA
                if self.elements['tables']:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("TABLE DATA (FULL EXTRACTION)\n")
                    f.write("=" * 60 + "\n\n")
                    
                    zero_tables = []
                    
                    for table in self.elements['tables']:
                        f.write(f"TABLE: {table['title']}\n")
                        f.write(f"  Category: {table['category']}\n")
                        if self.show_addresses:
                            z_axis = table['axes'].get('z', {})
                            if z_axis.get('address') is not None:
                                f.write(f"  Address: 0x{z_axis['address']:04X}\n")
                            elif table.get('address') is not None:
                                f.write(f"  Address: 0x{table['address']:04X}\n")
                        
                        # Write axis information with labels
                        axes = table['axes']
                        
                        if 'x' in axes:
                            x_axis = axes['x']
                            f.write(f"  X-Axis: {x_axis['count']} points")
                            if x_axis['unit']:
                                f.write(f" ({x_axis['unit']})")
                            f.write("\n")
                            
                            # Show ALL axis values
                            if x_axis.get('labels'):
                                x_decpl = x_axis.get('decimalpl', 2)
                                labels_str = ", ".join(
                                    self._format_value(v, x_decpl) for v in x_axis['labels']
                                )
                                f.write(f"    Values: [{labels_str}]\n")
                        
                        if 'y' in axes:
                            y_axis = axes['y']
                            f.write(f"  Y-Axis: {y_axis['count']} points")
                            if y_axis['unit']:
                                f.write(f" ({y_axis['unit']})")
                            f.write("\n")
                            
                            # Show ALL axis values
                            if y_axis.get('labels'):
                                y_decpl = y_axis.get('decimalpl', 2)
                                labels_str = ", ".join(
                                    self._format_value(v, y_decpl) for v in y_axis['labels']
                                )
                                f.write(f"    Values: [{labels_str}]\n")
                        
                        if 'z' in axes:
                            z_axis = axes['z']
                            if z_axis['unit']:
                                f.write(f"  Data Unit: {z_axis['unit']}\n")
                        
                        # Get decimal places for Z-axis (data values)
                        z_decimalpl = z_axis.get('decimalpl', 2)
                        
                        # Extract and validate table data
                        table_data = self._read_table_data(table)
                        
                        if table_data is not None:
                            # Apply axis flips
                            if self.flip_rpm or self.flip_load:
                                table_data, axes = (
                                    self._apply_axis_flips(
                                        table_data, axes))

                            validation = self._validate_table_data(
                                table, table_data
                            )
                            
                            # Show statistics
                            if ('stats' in validation
                                    and not self.no_stats):
                                stats = validation['stats']
                                f.write("  Statistics:\n")
                                f.write(
                                    f"    Min: "
                                    f"{self._format_value(stats['min'], z_decimalpl)}"
                                )
                                if z_axis.get('unit'):
                                    f.write(f" {z_axis['unit']}")
                                f.write("\n")
                                
                                f.write(
                                    f"    Max: "
                                    f"{self._format_value(stats['max'], z_decimalpl)}"
                                )
                                if z_axis.get('unit'):
                                    f.write(f" {z_axis['unit']}")
                                f.write("\n")
                                
                                f.write(
                                    f"    Avg: "
                                    f"{self._format_value(stats['avg'], z_decimalpl)}"
                                )
                                if z_axis.get('unit'):
                                    f.write(f" {z_axis['unit']}")
                                f.write("\n")
                                
                                f.write(
                                    f"    Unique Values: "
                                    f"{stats['unique_count']}\n"
                                )
                            
                            # Show warnings
                            if validation.get('warnings'):
                                for warning in validation['warnings']:
                                    f.write(f"  ⚠️ {warning}\n")
                                
                                if validation.get('all_zeros'):
                                    zero_tables.append(table['title'])
                            
                            # Output FULL data matrix (all rows and columns)
                            if len(table_data) > 0:
                                cols = len(table_data[0])
                                f.write(
                                    f"  Data Matrix "
                                    f"({len(table_data)} rows × {cols} cols):\n"
                                )
                                
                                # Get decimal places for formatting
                                z_decimalpl = z_axis.get('decimalpl', 2)
                                y_decimalpl = axes.get('y', {}).get(
                                    'decimalpl', 2
                                )
                                
                                # Output ALL rows (full export)
                                for i, row in enumerate(table_data):
                                    # Get Y-axis label for row if available
                                    y_label = ""
                                    if 'y' in axes:
                                        y_ax = axes['y']
                                        if y_ax.get('labels'):
                                            y_labels = y_ax['labels']
                                            if i < len(y_labels):
                                                y_val = y_labels[i]
                                                y_label = f" ({self._format_value(y_val, y_decimalpl)})"
                                    
                                    # Show ALL columns (no truncation)
                                    values_str = ", ".join(
                                        self._format_value(v, z_decimalpl)
                                        for v in row
                                    )
                                    
                                    f.write(
                                        f"    Row {i}{y_label}: "
                                        f"[{values_str}]\n"
                                    )
                        else:
                            f.write(
                                "  ⚠️ Could not extract table data "
                                "(address out of range)\n"
                            )
                        
                        f.write("\n")
                    
                    # Summary warnings for zero tables
                    if zero_tables:
                        f.write("\n" + "=" * 60 + "\n")
                        f.write("📊 ZERO-VALUE TABLES REPORT\n")
                        f.write("=" * 60 + "\n\n")
                        total = len(self.elements['tables'])
                        f.write(
                            f"Found {len(zero_tables)} of {total} "
                            f"tables with all-zero values:\n\n"
                        )
                        # Show ALL zero tables (not truncated)
                        for table_title in zero_tables:
                            f.write(f"  • {table_title}\n")
                        f.write(
                            "\n" + "-" * 60 + "\n"
                            "NOTE: Zero tables may indicate:\n"
                            "  1. XDF/BIN version mismatch (wrong definition file)\n"
                            "  2. Intentional OEM zeroing (e.g., Alpina B3 strategy)\n"
                            "  3. Unused features in this calibration variant\n"
                            "\nAlpina 'Zero Complex, Tune Simple' strategy intentionally\n"
                            "zeros interacting tables to force simpler fallback paths.\n"
                        )
                
                # Export PATCHES (Community Patchlist support)
                if self.elements['patches']:
                    f.write("\n" + "=" * 60 + "\n")
                    f.write("PATCHES (Community Patchlist)\n")
                    f.write("=" * 60 + "\n\n")
                    
                    # Group by status
                    applied = [p for p in self.elements['patches'] 
                               if p['status'] == 'applied']
                    not_applied = [p for p in self.elements['patches'] 
                                   if p['status'] == 'not_applied']
                    partial = [p for p in self.elements['patches'] 
                               if p['status'] == 'partial']
                    unknown = [p for p in self.elements['patches'] 
                               if p['status'] == 'unknown']
                    
                    # Summary
                    f.write(f"Total Patches: {len(self.elements['patches'])}\n")
                    f.write(f"  ✓ Applied: {len(applied)}\n")
                    f.write(f"  ✗ Not Applied: {len(not_applied)}\n")
                    if partial:
                        f.write(f"  ⚠ Partial: {len(partial)}\n")
                    if unknown:
                        f.write(f"  ? Unknown: {len(unknown)}\n")
                    f.write("\n" + "-" * 60 + "\n\n")
                    
                    # Applied patches
                    if applied:
                        f.write("✓ APPLIED PATCHES:\n")
                        f.write("-" * 40 + "\n")
                        for patch in applied:
                            f.write(f"  {patch['title']}\n")
                            if patch['description']:
                                f.write(f"    → {patch['description']}\n")
                        f.write("\n")
                    
                    # Not applied patches
                    if not_applied:
                        f.write("✗ NOT APPLIED PATCHES:\n")
                        f.write("-" * 40 + "\n")
                        for patch in not_applied:
                            f.write(f"  {patch['title']}\n")
                            if patch['description']:
                                f.write(f"    → {patch['description']}\n")
                        f.write("\n")
                    
                    # Partial patches (potential issues)
                    if partial:
                        f.write("⚠ PARTIALLY APPLIED PATCHES:\n")
                        f.write("-" * 40 + "\n")
                        for patch in partial:
                            f.write(f"  {patch['title']}\n")
                            f.write("    → WARNING: Patch may be corrupted or incompletely applied\n")
                        f.write("\n")
                
                self.logger.info(f"Export complete: {output_path}")
                return True
                
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return False
    
    def export_to_json(self, output_path: str) -> bool:
        """
        Export data to JSON format for programmatic use
        
        Args:
            output_path: Output JSON file path
            
        Returns:
            bool: True if successful
        """
        try:
            export_data = {
                'metadata': {
                    'source_file': self.bin_path.name,
                    'source_definition': self.definition_name,
                    'binary_size': self.bin_size,
                    'md5_checksum': self.bin_md5,
                    'export_timestamp': datetime.now().isoformat(),
                    'exporter_version': self.VERSION,
                    'author': self.AUTHOR_ALIAS,
                    'author_name': self.AUTHOR,
                    'author_github': self.AUTHOR_GITHUB
                },
                'statistics': {
                    'scalars_count': len(self.elements['constants']),
                    'flags_count': len(self.elements['flags']),
                    'tables_count': len(self.elements['tables']),
                    'patches_count': len(self.elements['patches'])
                },
                'scalars': [],
                'flags': [],
                'tables': [],
                'patches': []
            }
            
            # Export scalars
            for const in self.elements['constants']:
                raw_value = self.read_value_from_bin(
                    const['address'], const['size'],
                    signed=const.get('signed', False),
                    lsb_first=const.get('lsb_first', False)
                )
                if raw_value is None:
                    continue
                
                value = raw_value
                if const['equation']:
                    calc_value, _ = self.evaluate_math(
                        const['equation'], raw_value,
                        linked_vars=const.get(
                            'linked_vars', {}
                        )
                    )
                    if calc_value is not None:
                        value = calc_value
                
                decimalpl = const.get('decimalpl', 2)
                export_data['scalars'].append({
                    'title': const['title'],
                    'category': const['category'],
                    'address': f"0x{const['address']:04X}",
                    'raw_value': raw_value,
                    'value': round(value, decimalpl) if isinstance(value, float) else value,
                    'unit': const['unit'],
                    'equation': const['equation'],
                    'signed': const.get('signed', False),
                    'lsb_first': const.get('lsb_first', False),
                    'decimalpl': decimalpl
                })
            
            # Export flags
            for flag in self.elements['flags']:
                byte_value = self.read_value_from_bin(flag['address'], 8)
                if byte_value is None:
                    continue
                
                is_set = (byte_value & flag['mask']) != 0
                
                export_data['flags'].append({
                    'title': flag['title'],
                    'category': flag['category'],
                    'address': f"0x{flag['address']:04X}",
                    'mask': f"0x{flag['mask']:02X}",
                    'is_set': is_set
                })
            
            # Export tables with full data
            for table in self.elements['tables']:
                table_entry = {
                    'title': table['title'],
                    'category': table['category'],
                    'axes': {}
                }
                
                # Add axis info
                for axis_id, axis in table['axes'].items():
                    addr = axis['address']
                    addr_str = f"0x{addr:04X}" if addr is not None else None
                    table_entry['axes'][axis_id] = {
                        'count': axis['count'],
                        'unit': axis['unit'],
                        'address': addr_str,
                        'labels': axis.get('labels', []),
                        'equation': axis.get('equation', ''),
                        'decimalpl': axis.get('decimalpl', 2)
                    }
                
                # Get decimalpl from Z-axis for proper rounding
                z_axis = table.get('axes', {}).get('z', {})
                z_decimalpl = z_axis.get('decimalpl', 2)
                z_signed = z_axis.get('signed', False)
                z_lsb_first = z_axis.get('lsb_first', False)
                
                # Extract full table data
                table_data = self._read_table_data(table)
                if table_data is not None:
                    # Apply axis flips (uses deep copy)
                    flipped_axes = table['axes']
                    if self.flip_rpm or self.flip_load:
                        table_data, flipped_axes = (
                            self._apply_axis_flips(
                                table_data,
                                table['axes']))
                        # Update JSON labels
                        for aid in ('x', 'y'):
                            fa = flipped_axes.get(aid)
                            te = table_entry['axes'].get(
                                aid)
                            if fa and te and fa.get(
                                    'labels'):
                                te['labels'] = fa[
                                    'labels']

                    # Round values for JSON
                    table_entry['data'] = [
                        [round(v, z_decimalpl) for v in row]
                        for row in table_data
                    ]
                    table_entry['dimensions'] = {
                        'rows': len(table_data),
                        'cols': len(table_data[0]) if table_data else 0
                    }
                    table_entry['data_format'] = {
                        'signed': z_signed,
                        'lsb_first': z_lsb_first,
                        'decimalpl': z_decimalpl
                    }
                    
                    # Add statistics
                    if not self.no_stats:
                        flat = [v for row in table_data
                                for v in row]
                        if flat:
                            table_entry['statistics'] = {
                                'min': round(
                                    min(flat), z_decimalpl),
                                'max': round(
                                    max(flat), z_decimalpl),
                                'avg': round(
                                    statistics.mean(flat),
                                    z_decimalpl),
                                'unique_count': len(set(
                                    round(v, z_decimalpl)
                                    for v in flat))
                            }
                
                export_data['tables'].append(table_entry)
            
            # Export patches
            for patch in self.elements['patches']:
                patch_entry = {
                    'title': patch['title'],
                    'category': patch['category'],
                    'description': patch['description'],
                    'status': patch['status'],
                    'entries_count': len(patch['entries'])
                }
                export_data['patches'].append(patch_entry)
            
            # Write JSON
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"JSON export complete: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"JSON export failed: {e}")
            return False
    
    def export_to_markdown(self, output_path: str) -> bool:
        """
        Export data to Markdown format for documentation
        
        Args:
            output_path: Output Markdown file path
            
        Returns:
            bool: True if successful
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                # Header
                f.write(f"# ECU Calibration Export\n\n")
                f.write(f"## Metadata\n\n")
                f.write(f"| Property | Value |\n")
                f.write(f"|----------|-------|\n")
                f.write(f"| Source File | `{self.bin_path.name}` |\n")
                f.write(f"| Definition | `{self.definition_name}` |\n")
                f.write(f"| Binary Size | {self.bin_size:,} bytes |\n")
                f.write(f"| MD5 Checksum | `{self.bin_md5}` |\n")
                f.write(f"| Export Date | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
                f.write(f"| Exporter | KingAI TunerPro Exporter v{self.VERSION} |\n")
                f.write(f"| Author | {self.AUTHOR_ALIAS} ({self.AUTHOR}) |\n")
                f.write(f"| GitHub | [{self.AUTHOR_GITHUB}](https://github.com/{self.AUTHOR_GITHUB}) |\n\n")
                
                # Summary
                f.write(f"## Summary\n\n")
                f.write(f"- **Scalars:** {len(self.elements['constants'])}\n")
                f.write(f"- **Flags:** {len(self.elements['flags'])}\n")
                f.write(f"- **Tables:** {len(self.elements['tables'])}\n\n")
                
                # Table of Contents
                f.write(f"## Table of Contents\n\n")
                f.write(f"1. [Scalar Values](#scalar-values)\n")
                f.write(f"2. [Flags](#flags)\n")
                f.write(f"3. [Tables](#tables)\n\n")
                
                # Scalars
                f.write(f"---\n\n## Scalar Values\n\n")
                f.write(f"| Parameter | Value | Unit | Address | Category |\n")
                f.write(f"|-----------|-------|------|---------|----------|\n")
                
                for const in self.elements['constants']:
                    raw_value = self.read_value_from_bin(
                        const['address'], const['size']
                    )
                    if raw_value is None:
                        continue
                    
                    value = raw_value
                    if const['equation']:
                        calc_value, _ = self.evaluate_math(
                            const['equation'], raw_value,
                            linked_vars=const.get(
                                'linked_vars', {}
                            )
                        )
                        if calc_value is not None:
                            value = calc_value
                    
                    decimalpl = const.get('decimalpl', 2)
                    val_str = f"{value:.{decimalpl}f}" if isinstance(value, float) else str(value)
                    unit = const['unit'] or '-'
                    cat = const['category'] or 'Uncategorized'
                    title = const['title'].replace('|', '\\|')
                    addr_str = f"0x{const['address']:04X}" if const['address'] is not None else '-'
                    
                    f.write(f"| {title} | {val_str} | {unit} | {addr_str} | {cat} |\n")
                
                # Flags
                f.write(f"\n---\n\n## Flags\n\n")
                f.write(f"| Flag | Status | Category |\n")
                f.write(f"|------|--------|----------|\n")
                
                for flag in self.elements['flags']:
                    byte_value = self.read_value_from_bin(flag['address'], 8)
                    if byte_value is None:
                        continue
                    
                    is_set = (byte_value & flag['mask']) != 0
                    status = "✅ Set" if is_set else "❌ Not Set"
                    cat = flag['category'] or 'Uncategorized'
                    title = flag['title'].replace('|', '\\|')
                    
                    f.write(f"| {title} | {status} | {cat} |\n")
                
                # Tables
                f.write(f"\n---\n\n## Tables\n\n")
                
                for i, table in enumerate(self.elements['tables'], 1):
                    title = table['title']
                    f.write(f"### {i}. {title}\n\n")
                    
                    # Table metadata
                    f.write(f"**Category:** {table['category'] or 'Uncategorized'}\n\n")
                    
                    # Axes info
                    axes = table['axes']
                    if axes:
                        f.write(f"**Axes:**\n")
                        for axis_id, axis in axes.items():
                            axis_name = {'x': 'X-Axis', 'y': 'Y-Axis', 'z': 'Z-Axis (Data)'}.get(axis_id, axis_id)
                            unit = f" ({axis['unit']})" if axis['unit'] else ""
                            f.write(f"- {axis_name}: {axis['count']} points{unit}\n")
                        f.write("\n")
                    
                    # Extract table data
                    table_data = self._read_table_data(table)
                    if table_data is not None:
                        # Apply axis flips
                        if self.flip_rpm or self.flip_load:
                            table_data, axes = (
                                self._apply_axis_flips(
                                    table_data, axes))

                        # Statistics
                        flat = [v for row in table_data
                                for v in row]
                        if flat and not self.no_stats:
                            z_unit = axes.get('z', {}).get('unit', '')
                            z_dp = axes.get('z', {}).get('decimalpl', 2)
                            f.write(f"**Statistics:**\n")
                            f.write(f"- Min: {min(flat):.{z_dp}f} {z_unit}\n")
                            f.write(f"- Max: {max(flat):.{z_dp}f} {z_unit}\n")
                            f.write(f"- Avg: {statistics.mean(flat):.{z_dp}f} {z_unit}\n")
                            f.write(f"- Dimensions: {len(table_data)} × {len(table_data[0])}\n\n")
                        
                        # Full Data Table (all rows and columns)
                        if len(table_data) > 0 and len(table_data[0]) > 0:
                            cols = len(table_data[0])
                            z_decimalpl = axes.get('z', {}).get('decimalpl', 2)
                            y_decimalpl = axes.get('y', {}).get('decimalpl', 2)
                            
                            f.write(f"**Full Data Table** ({len(table_data)} rows × {cols} cols):\n\n")
                            
                            # Get X-axis labels for header if available
                            x_labels = axes.get('x', {}).get('labels', [])
                            x_decimalpl = axes.get('x', {}).get('decimalpl', 2)
                            
                            # Get Y-axis labels for row labels
                            y_labels = axes.get('y', {}).get('labels', [])
                            
                            # Header row with X-axis values
                            if x_labels:
                                f.write("| Y \\ X |")
                                for c, label in enumerate(x_labels[:cols]):
                                    f.write(f" {self._format_value(label, x_decimalpl)} |")
                                f.write("\n")
                            else:
                                f.write("| Row |")
                                for c in range(cols):
                                    f.write(f" C{c} |")
                                f.write("\n")
                            
                            # Separator row
                            f.write("|-----|")
                            for c in range(cols):
                                f.write("------|")
                            f.write("\n")
                            
                            # All data rows
                            for r, row_data in enumerate(table_data):
                                # Row label from Y-axis if available
                                if y_labels and r < len(y_labels):
                                    row_label = self._format_value(y_labels[r], y_decimalpl)
                                else:
                                    row_label = str(r)
                                
                                f.write(f"| {row_label} |")
                                for val in row_data:
                                    f.write(f" {self._format_value(val, z_decimalpl)} |")
                                f.write("\n")
                    
                    f.write("\n")
                
                # Export patches
                if self.elements['patches']:
                    f.write("\n---\n\n## Patches (Community Patchlist)\n\n")
                    
                    applied = [p for p in self.elements['patches'] 
                               if p['status'] == 'applied']
                    not_applied = [p for p in self.elements['patches'] 
                                   if p['status'] == 'not_applied']
                    
                    f.write(f"**Total Patches:** {len(self.elements['patches'])}\n")
                    f.write(f"- ✅ Applied: {len(applied)}\n")
                    f.write(f"- ❌ Not Applied: {len(not_applied)}\n\n")
                    
                    if applied:
                        f.write("### ✅ Applied Patches\n\n")
                        for patch in applied:
                            f.write(f"- **{patch['title']}**")
                            if patch['description']:
                                f.write(f": {patch['description']}")
                            f.write("\n")
                        f.write("\n")
                    
                    if not_applied:
                        f.write("### ❌ Not Applied Patches\n\n")
                        for patch in not_applied:
                            f.write(f"- **{patch['title']}**")
                            if patch['description']:
                                f.write(f": {patch['description']}")
                            f.write("\n")
                        f.write("\n")
                
                # Footer
                f.write("---\n\n")
                f.write(f"*Generated by KingAI TunerPro Exporter v{self.VERSION}*\n")
                f.write(f"*Author: {self.AUTHOR_ALIAS} ({self.AUTHOR})*\n")
            
            self.logger.info(f"Markdown export complete: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Markdown export failed: {e}")
            return False

    def export_to_csv(self, output_path: str) -> bool:
        """
        Export data to CSV format for spreadsheet analysis.

        Produces one row per scalar/flag and per table cell, with
        columns: Type, Category, Title, Address, RawValue, Value,
        Unit, Row, Col, RowLabel, ColLabel.

        Args:
            output_path: Output CSV file path

        Returns:
            bool: True if successful
        """
        import csv
        try:
            with open(output_path, 'w', newline='',
                       encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Type', 'Category', 'Title', 'Address',
                    'RawValue', 'Value', 'Unit',
                    'Row', 'Col', 'RowLabel', 'ColLabel'
                ])

                # Scalars
                for const in self.elements['constants']:
                    raw = self.read_value_from_bin(
                        const['address'], const['size'],
                        signed=const.get('signed', False),
                        lsb_first=const.get('lsb_first', False)
                    )
                    if raw is None:
                        continue
                    value = raw
                    if const['equation']:
                        cv, _ = self.evaluate_math(
                            const['equation'], raw,
                            linked_vars=const.get(
                                'linked_vars', {}
                            )
                        )
                        if cv is not None:
                            value = cv
                    dp = const.get('decimalpl', 2)
                    val_str = self._format_value(
                        value, dp) if isinstance(
                            value, float) else str(value)
                    addr = f"0x{const['address']:04X}"
                    writer.writerow([
                        'Scalar', const['category'],
                        const['title'], addr,
                        raw, val_str, const['unit'],
                        '', '', '', ''
                    ])

                # Flags
                for flag in self.elements['flags']:
                    bv = self.read_value_from_bin(
                        flag['address'], 8)
                    if bv is None:
                        continue
                    is_set = (bv & flag['mask']) != 0
                    addr = f"0x{flag['address']:04X}"
                    writer.writerow([
                        'Flag', flag['category'],
                        flag['title'], addr,
                        bv,
                        'Set' if is_set else 'Not Set',
                        f"mask=0x{flag['mask']:02X}",
                        '', '', '', ''
                    ])

                # Tables — one row per cell
                for table in self.elements['tables']:
                    axes = table['axes']
                    z_axis = axes.get('z', {})
                    z_addr = z_axis.get('address')
                    if z_addr is None:
                        continue
                    addr = f"0x{z_addr:04X}"
                    tdata = self._read_table_data(table)
                    if tdata is None:
                        continue
                    # Apply axis flips
                    if self.flip_rpm or self.flip_load:
                        tdata, axes = (
                            self._apply_axis_flips(
                                tdata, axes))
                        continue
                    y_labels = axes.get(
                        'y', {}).get('labels', [])
                    x_labels = axes.get(
                        'x', {}).get('labels', [])
                    z_dp = z_axis.get('decimalpl', 2)
                    z_unit = z_axis.get('unit', '')
                    for r, row in enumerate(tdata):
                        rl = (self._format_value(
                            y_labels[r],
                            axes.get('y', {}).get(
                                'decimalpl', 2))
                            if r < len(y_labels)
                            else str(r))
                        for c, val in enumerate(row):
                            cl = (self._format_value(
                                x_labels[c],
                                axes.get('x', {}).get(
                                    'decimalpl', 2))
                                if c < len(x_labels)
                                else str(c))
                            writer.writerow([
                                'Table',
                                table['category'],
                                table['title'],
                                addr,
                                '',
                                self._format_value(
                                    val, z_dp),
                                z_unit,
                                r, c, rl, cl
                            ])

            self.logger.info(
                f"CSV export complete: {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"CSV export failed: {e}")
            return False

    def export(self, output_path: str) -> bool:
        """
        Main export function - validates, parses, and exports
        
        Args:
            output_path: Output file path
            
        Returns:
            bool: True if successful
        """
        # Validate binary
        if not self.validate_bin_file():
            return False
        
        # Parse XDF
        if not self.parse_xdf():
            return False
        
        # Export to text
        return self.export_to_text(output_path)


def main():
    """Command-line interface with multi-format support"""
    # Filter out option flags for argument count check
    positional_args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if len(positional_args) < 3 or len(positional_args) > 4:
        print("=" * 70)
        print("  KingAI TunerPro XDF + BIN Universal Exporter")
        print("=" * 70)
        print(f"  Version: {__version__}")
        print(f"  Author:  {__author_alias__} ({__author__})")
        print(f"  GitHub:  {__author_github__}")
        print("=" * 70)
        print()
        print("Usage:")
        print(f"  python {sys.argv[0]} <xdf> <bin> <output> [format]")
        print()
        print("Formats:")
        print("  txt  - TunerPro-style text export (default)")
        print("  text - Same as txt")
        print("  json - JSON format for programmatic use")
        print("  md   - Markdown format for documentation")
        print("  csv  - Spreadsheet-compatible CSV format")
        print("  all  - Export all formats (txt, json, md, csv)")
        print()
        print("Options:")
        print("  --addresses    Include hex addresses in output (useful for XDF creation)")
        print("  --flip-rpm     Flip RPM axis (high-to-low instead of low-to-high)")
        print("  --flip-load    Flip load axis for presentation")
        print("  --no-stats     Omit statistical analysis from output")
        print()
        print("Examples:")
        print(f"  python {sys.argv[0]} def.xdf fw.bin out.txt")
        print(f"  python {sys.argv[0]} def.xdf fw.bin out.json json")
        print(f"  python {sys.argv[0]} def.xdf fw.bin export all")
        print(f"  python {sys.argv[0]} def.xdf fw.bin export.txt --flip-rpm")
        print()
        print("Features:")
        safe_print("  ✅ Full table data extraction (TunerPro fails at this!)")
        safe_print("  ✅ Axis label values displayed")
        safe_print("  ✅ Statistical analysis (min/max/avg)")
        safe_print("  ✅ Data integrity validation")
        safe_print("  ✅ Multiple output formats (TXT, JSON, MD, CSV)")
        safe_print("  ✅ Axis flip options for presentation preference")
        print()
        sys.exit(1)
    
    xdf_file = positional_args[0]
    bin_file = positional_args[1]
    output_base = positional_args[2]
    export_format = positional_args[3].lower() if len(positional_args) > 3 else 'txt'
    
    # Normalize format
    if export_format == 'text':
        export_format = 'txt'
    
    # Parse option flags
    show_addresses = '--addresses' in sys.argv
    flip_rpm = '--flip-rpm' in sys.argv
    flip_load = '--flip-load' in sys.argv
    no_stats = '--no-stats' in sys.argv
    
    # Create exporter
    exporter = UniversalXDFExporter(xdf_file, bin_file)
    exporter.show_addresses = show_addresses
    exporter.flip_rpm = flip_rpm
    exporter.flip_load = flip_load
    exporter.no_stats = no_stats
    
    # Validate and parse
    if not exporter.validate_bin_file():
        print("❌ Binary validation failed")
        sys.exit(1)
    
    if not exporter.parse_xdf():
        print("❌ XDF parsing failed")
        sys.exit(1)
    
    success = True
    outputs = []
    
    # Determine output paths and export
    base_path = Path(output_base)
    base_name = base_path.stem
    base_dir = base_path.parent
    
    if export_format in ('txt', 'all'):
        txt_path = base_dir / f"{base_name}.txt" if export_format == 'all' else output_base
        if exporter.export_to_text(str(txt_path)):
            outputs.append(('TXT', str(txt_path)))
        else:
            success = False
    
    if export_format in ('json', 'all'):
        json_path = base_dir / f"{base_name}.json" if export_format == 'all' else output_base
        if exporter.export_to_json(str(json_path)):
            outputs.append(('JSON', str(json_path)))
        else:
            success = False
    
    if export_format in ('md', 'markdown', 'all'):
        md_path = base_dir / f"{base_name}.md" if export_format == 'all' else output_base
        if exporter.export_to_markdown(str(md_path)):
            outputs.append(('Markdown', str(md_path)))
        else:
            success = False
    
    if export_format in ('csv', 'all'):
        csv_path = (base_dir / f"{base_name}.csv"
                    if export_format == 'all'
                    else output_base)
        if exporter.export_to_csv(str(csv_path)):
            outputs.append(('CSV', str(csv_path)))
        else:
            success = False
    
    # Summary
    print()
    print("=" * 70)
    if success and outputs:
        safe_print("✅ Export Successful!")
        print("=" * 70)
        print(f"Definition: {exporter.definition_name}")
        print(f"Binary: {exporter.bin_path.name}")
        print()
        print("Elements exported:")
        safe_print(f"  • {len(exporter.elements['constants'])} scalars")
        safe_print(f"  • {len(exporter.elements['flags'])} flags")
        safe_print(f"  • {len(exporter.elements['tables'])} tables")
        if exporter.elements['patches']:
            applied = len([p for p in exporter.elements['patches'] 
                          if p['status'] == 'applied'])
            total = len(exporter.elements['patches'])
            safe_print(f"  • {total} patches ({applied} applied)")
        print()
        print("Output files:")
        for fmt, path in outputs:
            print(f"  [{fmt}] {path}")
        print()
        print(f"Exporter: KingAI TunerPro Exporter v{__version__}")
        print(f"Author: {__author_alias__} ({__author__})")
        sys.exit(0)
    else:
        safe_print("❌ Export Failed - Check log messages above")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()

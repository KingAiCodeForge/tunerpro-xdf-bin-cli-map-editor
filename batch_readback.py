"""Validate a staged XDF cell using the Exporter's own conversion resolution.

A parallel conversion implementation risks validating a different equation or
stale linked variables than the parser uses to display a table. Reuse the
pinned Exporter's cell selector and axis context when these are available.
The small fallback exists solely for dependency-free fake-session regressions.
"""
from __future__ import annotations

import math


def decoded_table_cell(session, item: dict, row: int, col: int, raw: int | float):
    """Return the exact staged cell's engineering value, or refuse ambiguity.

    `row` and `col` are 1-based. A real Exporter must be given the staged BIN
    while resolving linked math and axis values. Always restore its previous
    `bin_data`, even if resolution raises an exception.
    """
    if type(row) is not int or type(col) is not int or row < 1 or col < 1:
        raise ValueError('Table readback requires positive 1-based cell indices')
    z = item['axes']['z']
    exporter = session.exporter
    if callable(getattr(exporter, '_cell_equation_selector', None)):
        if not callable(getattr(exporter, 'table_context', None)):
            raise ValueError('Exporter cell selector lacks a table context resolver')
        original = exporter.bin_data
        exporter.bin_data = session.bin_data  # struct.unpack_from reads bytearray without copying a whole BIN
        try:
            selector = exporter._cell_equation_selector(z)
            equation, linked_vars, math_element = selector(row - 1, col - 1)
            context = exporter.table_context(item, row - 1, col - 1)
            value, _ = exporter.evaluate_math(
                equation, raw, context, linked_vars=linked_vars,
                math_element=math_element)
        finally:
            exporter.bin_data = original
    else:
        # Existing isolated fake sessions exercise the coordinator without
        # installing the Exporter. Production always takes the branch above.
        variables = session._current_variables(z, item, row - 1, col - 1)
        value, _ = exporter.evaluate_math(z.get('equation', ''), raw, linked_vars=variables)
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Final XDF cell conversion is missing or nonfinite')
    return value

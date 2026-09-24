"""Regression coverage for native TunerPro overlapping axis strides."""

import xml.etree.ElementTree as ET
import pytest

from tunerpro_exporter_for_cli_editor_version import UniversalXDFExporter


def test_embedded_axis_honors_stride_smaller_than_element_width():
    exporter = UniversalXDFExporter("unused.xdf", "unused.bin")
    exporter.bin_data = bytes(0x20) + bytes((0x01, 0x02, 0x03, 0x04, 0x05))
    exporter.bin_size = len(exporter.bin_data)

    axis = ET.fromstring(
        """
        <XDFAXIS id="x">
          <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x20"
              mmedelementsizebits="16" mmedmajorstridebits="8"
              mmedminorstridebits="0" />
          <indexcount>4</indexcount>
          <embedinfo type="1" />
          <MATH equation="X"><VAR id="X" /></MATH>
        </XDFAXIS>
        """
    )

    assert exporter._resolve_embedded_axis_values(axis) == [
        258.0,
        515.0,
        772.0,
        1029.0,
    ]


def test_embedded_axis_rejects_non_byte_aligned_stride():
    exporter = UniversalXDFExporter("unused.xdf", "unused.bin")
    exporter.bin_data = bytes(0x40)
    exporter.bin_size = len(exporter.bin_data)

    axis = ET.fromstring(
        """
        <XDFAXIS id="x">
          <EMBEDDEDDATA mmedtypeflags="0x00" mmedaddress="0x20"
              mmedelementsizebits="16" mmedmajorstridebits="12"
              mmedminorstridebits="0" />
          <indexcount>2</indexcount>
          <embedinfo type="1" />
          <MATH equation="X"><VAR id="X" /></MATH>
        </XDFAXIS>
        """
    )

    with pytest.raises(ValueError, match="byte-aligned"):
        exporter._resolve_embedded_axis_values(axis)

"""Regression coverage for both TunerPro CATEGORYMEM conventions."""

import xml.etree.ElementTree as ET

from tunerpro_exporter_for_cli_editor_version import UniversalXDFExporter


def exporter_for(xml: str) -> UniversalXDFExporter:
    exporter = UniversalXDFExporter("unused.xdf", "unused.bin")
    exporter.xdf_root = ET.fromstring(xml)
    exporter._extract_categories()
    return exporter


def test_detects_one_based_category_membership():
    exporter = exporter_for(
        """<XDFFORMAT><XDFHEADER>
        <CATEGORY index="0" name="Fuel"/><CATEGORY index="1" name="Ignition"/>
        </XDFHEADER>
        <XDFCONSTANT><CATEGORYMEM category="1"/></XDFCONSTANT>
        <XDFCONSTANT><CATEGORYMEM category="2"/></XDFCONSTANT>
        </XDFFORMAT>"""
    )
    elements = exporter.xdf_root.findall("XDFCONSTANT")
    assert exporter.category_member_offset == -1
    assert [exporter._get_category_name(item) for item in elements] == [
        "Fuel",
        "Ignition",
    ]


def test_preserves_direct_category_membership():
    exporter = exporter_for(
        """<XDFFORMAT><XDFHEADER>
        <CATEGORY index="1" name="Fuel"/><CATEGORY index="2" name="Ignition"/>
        </XDFHEADER>
        <XDFCONSTANT><CATEGORYMEM category="1"/></XDFCONSTANT>
        <XDFCONSTANT><CATEGORYMEM category="2"/></XDFCONSTANT>
        </XDFFORMAT>"""
    )
    elements = exporter.xdf_root.findall("XDFCONSTANT")
    assert exporter.category_member_offset == 0
    assert [exporter._get_category_name(item) for item in elements] == [
        "Fuel",
        "Ignition",
    ]

#!/usr/bin/env python3
"""Test parse_child_text behavior."""
from xml.etree import ElementTree as ET

xml = """<atom:entry xmlns:ns="http://naesb.org/espi" xmlns:atom="http://www.w3.org/2005/Atom">
<atom:content>
<ns:UsagePoint>
<ns:ServiceCategory>
<ns:kind>0</ns:kind>
</ns:ServiceCategory>
</ns:UsagePoint>
</atom:content>
</atom:entry>"""

_NAMESPACE_MAP = {
    "atom": "http://www.w3.org/2005/Atom",
    "espi": "http://naesb.org/espi",
    "ns": "http://naesb.org/espi",
}

root = ET.fromstring(xml)

# Get the UsagePoint element first
content_elem = root.find("./atom:content", _NAMESPACE_MAP)
print(f"Content element: {content_elem}")

usage_point = content_elem.find("./ns:UsagePoint", _NAMESPACE_MAP)
print(f"UsagePoint element found with ns: {usage_point}")

usage_point = content_elem.find("./espi:UsagePoint", _NAMESPACE_MAP)
print(f"UsagePoint element found with espi: {usage_point}")

# Now try to find the kind
if usage_point is not None:
    kind_espi = usage_point.find("./espi:ServiceCategory/espi:kind", _NAMESPACE_MAP)
    print(f"\nSearching for espi:ServiceCategory/espi:kind: {kind_espi}")
    if kind_espi is not None:
        print(f"  Value: {kind_espi.text}")
    
    kind_ns = usage_point.find("./ns:ServiceCategory/ns:kind", _NAMESPACE_MAP)
    print(f"\nSearching for ns:ServiceCategory/ns:kind: {kind_ns}")
    if kind_ns is not None:
        print(f"  Value: {kind_ns.text}")

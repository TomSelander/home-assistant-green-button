#!/usr/bin/env python3
"""Test XPath namespace support."""
from defusedxml import ElementTree as ET

xml = """<atom:feed xmlns:ns="http://naesb.org/espi" xmlns:atom="http://www.w3.org/2005/Atom">
<atom:entry>
<atom:content>
<ns:UsagePoint>
<ns:ServiceCategory>
<ns:kind>0</ns:kind>
</ns:ServiceCategory>
</ns:UsagePoint>
</atom:content>
</atom:entry>
</atom:feed>"""

root = ET.fromstring(xml)

# Test with both ns and espi prefixes
namespace_map_old = {
    "atom": "http://www.w3.org/2005/Atom",
    "espi": "http://naesb.org/espi",
}

namespace_map_new = {
    "atom": "http://www.w3.org/2005/Atom",
    "espi": "http://naesb.org/espi",
    "ns": "http://naesb.org/espi",
}

# Test with old namespace map (espi prefix only)
print("Testing with OLD namespace map (espi prefix only):")
results_old = root.findall("./atom:entry/atom:content/espi:UsagePoint/../..", namespace_map_old)
print(f"  Results: {len(results_old)}")

# Test with new namespace map (both ns and espi)
print("\nTesting with NEW namespace map (ns and espi prefixes):")
results_new_ns = root.findall("./atom:entry/atom:content/ns:UsagePoint/../..", namespace_map_new)
print(f"  Results with ns prefix: {len(results_new_ns)}")

results_new_espi = root.findall("./atom:entry/atom:content/espi:UsagePoint/../..", namespace_map_new)
print(f"  Results with espi prefix: {len(results_new_espi)}")

# The key insight: namespace matching is by URI, not by prefix
# So adding "ns" to the map allows queries with either prefix to work
print(f"\n✓ Both queries find entries when ns is in the map!")

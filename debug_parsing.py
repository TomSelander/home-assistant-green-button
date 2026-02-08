#!/usr/bin/env python3
"""Standalone debug script to test XML parsing without Home Assistant."""
from xml.etree import ElementTree as ET

xml = """<atom:feed xmlns:ns="http://naesb.org/espi" xmlns:atom="http://www.w3.org/2005/Atom">
<atom:id>urn:uuid:046638c0-8701-11e0-9d78-0800200c9a66</atom:id>
<atom:entry>
<atom:content>
<ns:UsagePoint>
<ns:ServiceCategory>
<ns:kind>0</ns:kind>
</ns:ServiceCategory>
<ns:status>1</ns:status>
</ns:UsagePoint>
</atom:content>
<atom:id>urn:uuid:046638c0-8701-11e0-9d78-0800200c9a66</atom:id>
<atom:link href="User/9b6c7063/UsagePoint/01" rel="self"/>
</atom:entry>
</atom:feed>"""

print("=" * 60)
print("Testing XPath queries with different namespace configurations")
print("=" * 60)

root = ET.fromstring(xml)

# Test 1: Old namespace map (only espi prefix)
namespace_map_old = {
    "atom": "http://www.w3.org/2005/Atom",
    "espi": "http://naesb.org/espi",
}

print("\n1. Testing with OLD namespace map (espi prefix only):")
print(f"   Namespace map: {namespace_map_old}")

results = root.findall("./atom:entry/atom:content/espi:UsagePoint/../..", namespace_map_old)
print(f"   XPath: ./atom:entry/atom:content/espi:UsagePoint/../..")
print(f"   Results: {len(results)} entry(ies) found")

# Test 2: New namespace map (both ns and espi)
namespace_map_new = {
    "atom": "http://www.w3.org/2005/Atom",
    "espi": "http://naesb.org/espi",
    "ns": "http://naesb.org/espi",
}

print("\n2. Testing with NEW namespace map (ns and espi prefixes):")
print(f"   Namespace map: {namespace_map_new}")

results = root.findall("./atom:entry/atom:content/espi:UsagePoint/../..", namespace_map_new)
print(f"   XPath: ./atom:entry/atom:content/espi:UsagePoint/../..")
print(f"   Results: {len(results)} entry(ies) found")

# Test 3: Try with ns prefix in XPath
print("\n3. Testing with ns prefix in XPath:")
results = root.findall("./atom:entry/atom:content/ns:UsagePoint/../..", namespace_map_new)
print(f"   XPath: ./atom:entry/atom:content/ns:UsagePoint/../..")
print(f"   Results: {len(results)} entry(ies) found")

# Test 4: Direct element matching (no ancestor traversal)
print("\n4. Testing direct element matching:")
results = root.findall("./atom:entry/atom:content/ns:UsagePoint", namespace_map_new)
print(f"   XPath: ./atom:entry/atom:content/ns:UsagePoint")
print(f"   Results: {len(results)} element(s) found")
if results:
    for i, elem in enumerate(results):
        print(f"     Element {i}: {elem.tag}")

# Test 5: Try alternative XPath without ancestor traversal
print("\n5. Alternative XPath approach (entry with ns:UsagePoint in content):")
results = root.findall(".//atom:entry[atom:content/ns:UsagePoint]", namespace_map_new)
print(f"   XPath: .//atom:entry[atom:content/ns:UsagePoint]")
print(f"   Results: {len(results)} entry(ies) found")

print("\n" + "=" * 60)
print("ANALYSIS:")
print("=" * 60)
if len(root.findall("./atom:entry/atom:content/espi:UsagePoint/../..", namespace_map_new)) > 0:
    print("✓ XPath works with espi: prefix even though XML uses ns: prefix")
else:
    print("✗ XPath does NOT work - namespace mapping issue detected!")
    print("  The find_entries() method needs to be updated to use 'ns:' prefix")

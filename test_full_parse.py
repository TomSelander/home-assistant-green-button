#!/usr/bin/env python3
"""Comprehensive test of the parsing flow."""
from xml.etree import ElementTree as ET
from defusedxml import ElementTree as defusedET

# Minimal version of the key parsing logic
_NAMESPACE_MAP = {
    "atom": "http://www.w3.org/2005/Atom",
    "espi": "http://naesb.org/espi",
    "ns": "http://naesb.org/espi",
}

def find_entries(root, entry_type_tag):
    """Find entries of a given type."""
    entries = []
    for elem in root.findall(f"./atom:entry/atom:content/espi:{entry_type_tag}/../..", _NAMESPACE_MAP):
        # Get the self href
        links = elem.findall("./atom:link[@rel='self']", _NAMESPACE_MAP)
        if links:
            href = links[0].get("href")
            entries.append((href, elem))
    return entries

def parse_child_text(elem, xpath, converter):
    """Parse child element text."""
    match = elem.find(xpath, _NAMESPACE_MAP)
    if match is None or match.text is None:
        raise ValueError(f"Element not found at {xpath}")
    return converter(match.text)

xml_data = """<atom:feed xmlns:ns="http://naesb.org/espi" xmlns:atom="http://www.w3.org/2005/Atom">
<atom:id>urn:uuid:046638c0-8701-11e0-9d78-0800200c9a66</atom:id>
<atom:link href="/ThirdParty/83e269c1/Batch" rel="self"/>
<atom:title>ThirdPartyX Batch Feed</atom:title>
<atom:updated>2026-02-07T07:28:36</atom:updated>
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
<atom:link href="User/9b6c7063/UsagePoint" rel="up"/>
<atom:link href="User/9b6c7063/UsagePoint/01/MeterReading" rel="related"/>
<atom:link href="User/9b6c7063/UsagePoint/01/ElectricPowerUsageSummary" rel="related"/>
<atom:link href="LocalTimeParameters/01" rel="related"/>
<atom:published>2026-02-07T07:28:36</atom:published>
<atom:title>145 CUSHMAN DR, MANCHESTER , CT 06042</atom:title>
<atom:updated>2026-02-07T07:28:36</atom:updated>
</atom:entry>
<atom:entry>
<atom:content>
<ns:MeterReading/>
</atom:content>
<atom:id>urn:uuid:046638c0-8701-11e0-9d78-0800200c9a66</atom:id>
<atom:link href="User/9b6c7063/UsagePoint/01/MeterReading/01" rel="self"/>
<atom:link href="User/9b6c7063/UsagePoint/01/MeterReading" rel="up"/>
<atom:link href="User/9b6c7063/UsagePoint/01/MeterReading/01/IntervalBlock" rel="related"/>
<atom:link href="ReadingType/07" rel="related"/>
<atom:published>2026-02-07T07:28:36</atom:published>
<atom:title>Monthly Energy Consumption</atom:title>
<atom:updated>2026-02-07T07:28:36</atom:updated>
</atom:entry>
<atom:entry>
<atom:content>
<ns:ReadingType>
<ns:accumulationBehaviour>4</ns:accumulationBehaviour>
<ns:commodity>1</ns:commodity>
<ns:currency>840</ns:currency>
<ns:dataQualifier>12</ns:dataQualifier>
<ns:flowDirection>1</ns:flowDirection>
<ns:intervalLength>2678400</ns:intervalLength>
<ns:kind>12</ns:kind>
<ns:phase>0</ns:phase>
<ns:powerOfTenMultiplier>0</ns:powerOfTenMultiplier>
<ns:timeAttribute>0</ns:timeAttribute>
<ns:uom>72</ns:uom>
</ns:ReadingType>
</atom:content>
<atom:id>urn:uuid:046638c0-8701-11e0-9d78-0800200c9a66</atom:id>
<atom:link href="ReadingType/07" rel="self"/>
<atom:link href="ReadingType" rel="up"/>
<atom:published>2026-02-07T07:28:36</atom:published>
<atom:title>Energy Delivered (kWh)</atom:title>
<atom:updated>2026-02-07T07:28:36</atom:updated>
</atom:entry>
</atom:feed>"""

print("=" * 70)
print("COMPREHENSIVE PARSING TEST")
print("=" * 70)

try:
    root = defusedET.fromstring(xml_data)
    print("\n✓ XML parsed successfully")
    
    # Step 1: Find UsagePoint entries
    print("\n1. Finding UsagePoint entries...")
    up_entries = find_entries(root, "UsagePoint")
    print(f"   Found {len(up_entries)} UsagePoint entries")
    for i, (href, elem) in enumerate(up_entries):
        print(f"     [{i}] {href}")
        
        # Step 2: Parse ServiceCategory/kind
        try:
            kind = parse_child_text(elem.find("./atom:content", _NAMESPACE_MAP), "espi:UsagePoint/espi:ServiceCategory/espi:kind", int)
            print(f"         ServiceCategory/kind: {kind}")
        except Exception as e:
            print(f"         ERROR parsing kind: {e}")
    
    # Step 3: Find MeterReading entries
    print("\n2. Finding MeterReading entries...")
    mr_entries = find_entries(root, "MeterReading")
    print(f"   Found {len(mr_entries)} MeterReading entries")
    for i, (href, elem) in enumerate(mr_entries):
        print(f"     [{i}] {href}")
    
    # Step 4: Find ReadingType entries
    print("\n3. Finding ReadingType entries...")
    rt_entries = find_entries(root, "ReadingType")
    print(f"   Found {len(rt_entries)} ReadingType entries")
    for i, (href, elem) in enumerate(rt_entries):
        print(f"     [{i}] {href}")
        
        # Parse flowDirection
        try:
            content_elem = elem.find("./atom:content", _NAMESPACE_MAP)
            flow_dir = parse_child_text(content_elem, "espi:ReadingType/espi:flowDirection", int)
            interval_len = parse_child_text(content_elem, "espi:ReadingType/espi:intervalLength", int)
            print(f"         flowDirection: {flow_dir}, intervalLength: {interval_len}")
        except Exception as e:
            print(f"         ERROR: {e}")
    
    print("\n" + "=" * 70)
    print("SUMMARY: If all entries found and values parsed, parsing logic works!")
    print("=" * 70)
    
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()

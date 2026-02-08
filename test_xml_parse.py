#!/usr/bin/env python3
"""Test script to debug XML parsing."""
import logging
from custom_components.green_button.parsers.espi import parse_xml

logging.basicConfig(level=logging.DEBUG)

xml = """<atom:feed xmlns:ns="http://naesb.org/espi" xmlns:atom="http://www.w3.org/2005/Atom">
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
<ns:IntervalBlock>
<ns:interval>
<ns:duration>2592000</ns:duration>
<ns:start>1735603200</ns:start>
</ns:interval>
<ns:IntervalReading>
<ns:cost>16563000</ns:cost>
<ns:ReadingQuality>
<ns:quality>0</ns:quality>
</ns:ReadingQuality>
<ns:timePeriod>
<ns:duration>2592000</ns:duration>
<ns:start>1735603200</ns:start>
</ns:timePeriod>
<ns:value>496000</ns:value>
</ns:IntervalReading>
</ns:IntervalBlock>
</atom:content>
<atom:id>urn:uuid:046638c0-8701-11e0-9d78-0800200c9a66</atom:id>
<atom:link href="User/9b6c7063/UsagePoint/01/MeterReading/01/IntervalBlock/0173" rel="self"/>
<atom:link href="User/9b6c7063/UsagePoint/01/MeterReading/01/IntervalBlock" rel="up"/>
<atom:published>2026-02-07T07:28:36</atom:published>
<atom:title/>
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
<atom:entry>
<atom:content>
<ns:ElectricPowerUsageSummary>
<ns:billingPeriod>
<ns:duration>2592000</ns:duration>
<ns:start>1735603200</ns:start>
</ns:billingPeriod>
<ns:billLastPeriod>16563000</ns:billLastPeriod>
<ns:billToDate>196604000</ns:billToDate>
<ns:costAdditionalLastPeriod>0</ns:costAdditionalLastPeriod>
<ns:currency>840</ns:currency>
<ns:overallConsumptionLastPeriod>
<ns:powerOfTenMultiplier>0</ns:powerOfTenMultiplier>
<ns:timeStamp>1738195200</ns:timeStamp>
<ns:uom>72</ns:uom>
<ns:value>496000</ns:value>
</ns:overallConsumptionLastPeriod>
<ns:currentBillingPeriodOverAllConsumption>
<ns:powerOfTenMultiplier>0</ns:powerOfTenMultiplier>
<ns:timeStamp>1738195200</ns:timeStamp>
<ns:uom>72</ns:uom>
<ns:value>6802000</ns:value>
</ns:currentBillingPeriodOverAllConsumption>
<ns:qualityOfReading>14</ns:qualityOfReading>
<ns:statusTimeStamp>1738195200</ns:statusTimeStamp>
</ns:ElectricPowerUsageSummary>
</atom:content>
<atom:id>urn:uuid:046638c0-8701-11e0-9d78-0800200c9a66</atom:id>
<atom:link href="User/9b6c7063/ElectricPowerUsageSummary/01" rel="self"/>
<atom:link href="User/9b6c7063/UsagePoint/01/ElectricPowerUsageSummary" rel="up"/>
<atom:published>2026-02-07T07:28:36</atom:published>
<atom:title>Usage Summary</atom:title>
<atom:updated>2026-02-07T07:28:36</atom:updated>
</atom:entry>
</atom:feed>"""

try:
    result = parse_xml(xml)
    print(f"\n✓ Successfully parsed {len(result)} usage points")
    for i, up in enumerate(result):
        print(f"\nUsagePoint {i}: {up.id}")
        print(f"  Device Class: {up.sensor_device_class}")
        print(f"  Meter Readings: {len(up.meter_readings)}")
        for j, mr in enumerate(up.meter_readings):
            print(f"    MeterReading {j}: {mr.id}")
            print(f"      Interval Blocks: {len(mr.interval_blocks)}")
except Exception as e:
    import traceback
    print("\n✗ Error parsing XML:")
    traceback.print_exc()

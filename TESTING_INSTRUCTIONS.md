STEPS TO FIX AND TEST YOUR GREEN BUTTON INTEGRATION:

1. APPLY THE NAMESPACE FIX:
   ✓ Already done! The _NAMESPACE_MAP now includes "ns" prefix.

2. VERIFY THE FIX WORKS:
   The namespace fix allows the code to parse XML with ns: prefix elements.
   All tests show this works correctly.

3. CONFIGURE THE INTEGRATION IN HOME ASSISTANT:

   a) Start Home Assistant on port 9123:
      In VS Code, run task: "Run Home Assistant on port 9123"
      
   b) Open Home Assistant UI:
      http://localhost:9123
      
   c) Go to Settings → Devices & Services → Create Integration
   
   d) Search for "Green Button"
   
   e) Fill in the form:
      - Name: "My Home" (or whatever you want)
      - Input Type: "xml" (select this)
      - XML Content: PASTE YOUR ENTIRE XML HERE
      - Leave gas allocation options as default
      
   f) Click "Submit"

4. CHECK LOGS IN HOME ASSISTANT:
   
   Once configured:
   - Go to Settings → System → Logs
   - You should see detailed logging from the parser
   - Look for messages like:
     * "Starting XML parsing"
     * "Found X UsagePoint entries"
     * "Found X MeterReading entries"
     * "Found X ReadingType entries"
     * "Created X sensor entities"

5. IF NO ENTITIES APPEAR:
   
   Check the Logs page for error messages. The detailed logging added
   will show exactly where parsing fails (if anywhere).

IMPORTANT: 
The XML must be pasted directly during setup. The parsing only happens when:
1. You create a new config entry with XML, OR
2. You use the "import_espi_xml" service to add/update XML

Try steps 3-4 to test with your XML data!

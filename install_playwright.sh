#!/bin/bash
# Install Playwright for Home Assistant Green Button integration
# Run this from Home Assistant Terminal add-on

set -e

echo "Installing Playwright for Green Button integration..."
echo ""

# Try different ways to access pip
if command -v pip &> /dev/null; then
    echo "Found pip, installing..."
    pip install playwright
    playwright install chromium
elif command -v pip3 &> /dev/null; then
    echo "Found pip3, installing..."
    pip3 install playwright
    pip3 install playwright install chromium
elif command -v python -m pip &> /dev/null; then
    echo "Using python -m pip..."
    python -m pip install playwright
    python -m pip install playwright install chromium
elif command -v python3 -m pip &> /dev/null; then
    echo "Using python3 -m pip..."
    python3 -m pip install playwright
    python3 -m pip install playwright install chromium
else
    echo "ERROR: Could not find pip or python"
    echo ""
    echo "Home Assistant OS may have pip access restricted."
    echo "You may need to:"
    echo "1. Switch to Home Assistant Container (Docker) for more control"
    echo "2. Or run Home Assistant in a virtual environment where pip is available"
    exit 1
fi

echo ""
echo "✓ Playwright installed successfully!"
echo ""
echo "Next steps:"
echo "1. Restart Home Assistant"
echo "2. Go to Settings > Devices & Services"
echo "3. Click 'Create Integration'"
echo "4. Search for 'Green Button'"
echo "5. Enter your Eversource credentials"
echo ""

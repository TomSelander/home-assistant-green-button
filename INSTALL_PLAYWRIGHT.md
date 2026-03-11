# Installing Playwright for Green Button Integration

The Green Button integration uses Playwright to handle Eversource's JavaScript-based login. If you get an error about Playwright not being installed, follow these steps.

## Home Assistant OS (Raspberry Pi)

### Method 1: Terminal Add-on (Recommended)

1. **Open Home Assistant Terminal add-on**
2. **Run one of these commands:**

```bash
# Try standard pip first
pip install playwright && playwright install chromium

# Or use python module syntax
python -m pip install playwright && python -m pip install playwright install chromium

# Or with python3
python3 -m pip install playwright && python3 -m pip install playwright install chromium
```

3. **Restart Home Assistant** (Settings > System > Restart Home Assistant)
4. **Try adding the integration again** (Settings > Devices & Services > Create Integration > Green Button)

### Method 2: Automated Script

Run the included installation script:

```bash
# On Linux/Raspberry Pi
bash /config/custom_components/green_button/install_playwright.sh

# Or manually copy the script into Terminal add-on and run it
```

### Method 3: Home Assistant Container (Docker)

If pip is restricted in Home Assistant OS, consider using Home Assistant Container instead:

1. Switch to [Home Assistant Container](https://www.home-assistant.io/installation/linux#docker-compose) installation
2. You'll have full access to pip and system commands
3. Run: `pip install playwright && playwright install chromium`

## Home Assistant Supervised / Virtual Environment

```bash
# Access the Home Assistant venv
source /srv/homeassistant/bin/activate
pip install playwright
playwright install chromium
```

## Troubleshooting

### "Command not found: pip"
- Home Assistant OS may have restricted pip access
- Try `python -m pip` or `python3 -m pip` instead
- Or switch to Home Assistant Container (Docker)

### "pip: command not found" in all forms
- Your Home Assistant OS installation doesn't allow pip access
- This is a security restriction by Home Assistant OS
- Solutions:
  1. Use Home Assistant Container (Docker) instead - gives you full system access
  2. Run Home Assistant in a virtual environment on your Pi
  3. Contact Home Assistant community for guidance on your specific setup

### "playwright install chromium" hangs or fails
- ARM64 Chromium is large (~300-400 MB)
- This may take 5-10 minutes
- If it fails, try again - network timeouts can occur on Raspberry Pi
- Check available disk space: `df -h /`

### Integration still shows "Playwright not installed" error
1. Verify installation: `pip show playwright`
2. Verify Chromium installed: `ls ~/.cache/ms-playwright/`
3. Restart Home Assistant completely (not just reload)
4. Check Home Assistant logs (Settings > System > Logs)

## What This Installs

- **playwright** (~150 MB) - Python library for browser automation
- **chromium** (~400 MB) - Headless browser engine (one-time download)

Total disk usage: ~550 MB (one-time)

## After Installation

Once installed successfully:

1. Go to **Settings > Devices & Services**
2. Click **Create Integration**
3. Search for **Green Button**
4. Enter your Eversource username and password
5. The integration will validate your credentials and start polling for usage data

The integration will fetch your Eversource usage data every 12 hours and make it available as Home Assistant sensors.

## Questions?

If you're still having issues:

1. Check [Home Assistant documentation](https://www.home-assistant.io/installation/)
2. Check [Playwright Python documentation](https://playwright.dev/python/)
3. Open an issue on the [GitHub repository](https://github.com/vqvu/home-assistant-green-button/issues)

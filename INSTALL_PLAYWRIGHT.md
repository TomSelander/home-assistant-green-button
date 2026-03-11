# Installing Playwright for Green Button Integration

The Green Button integration uses Playwright to handle Eversource's JavaScript-based login. If you get an error about Playwright not being installed, follow these steps.

## ⚠️ Home Assistant OS (Raspberry Pi) - NOT SUPPORTED

**Playwright cannot be installed on Home Assistant OS running on Raspberry Pi** due to ARM64 musl libc incompatibility. This is a fundamental limitation:

- Playwright wheels are only available for glibc-based systems (x86, x64, ARM64 Debian/Ubuntu)
- Raspberry Pi Home Assistant OS uses Alpine Linux with musl libc
- No amount of `pip install` tweaking will resolve this

**This limitation applies to all Raspberry Pi Home Assistant OS installations.**

### ✅ Solutions:

#### Option 1: Switch to Home Assistant Container (Docker) - RECOMMENDED

1. Backup your Home Assistant configuration
2. Switch to [Home Assistant Container](https://www.home-assistant.io/installation/linux#docker-compose) installation (Docker on your Pi)
3. Docker provides glibc, so Playwright will install normally:
   ```bash
   pip install playwright && playwright install chromium
   ```
4. Restore your configuration

Home Assistant Container is lighter weight than OS and gives you full system access.

#### Option 2: Run Home Assistant on a Different Device

- Install Home Assistant OS or Home Assistant (generic Linux) on any x86/x64 or ARM64 Debian/Ubuntu system
- Playwright works perfectly on these architectures
- Examples: old laptop, desktop PC, cloud VPS, or x86 NAS

#### Option 3: Use Non-Raspberry Pi Home Assistant

If you're building a new system, consider:
- x86-based single-board computer (Intel NUC, etc.)
- Traditional laptop/desktop running Home Assistant
- Cloud-hosted Home Assistant
- x86 NAS running Home Assistant

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

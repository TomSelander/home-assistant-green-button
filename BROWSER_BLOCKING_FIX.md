# Browser Blocking / Anti-Bot Detection & Fix

## Problem Identification

You can access Eversource fine in your browser, but the scraper can't log in. This is a classic sign of **anti-bot measures** blocking the scraper.

### Why This Happens

Websites like Eversource use security measures to block automated requests:
- **User-Agent detection** — Requests that don't look like real browsers
- **Header validation** — Missing standard browser headers
- **Referer checking** — Form posts without proper Referer headers
- **Cloudflare/similar services** — Checking for bot signatures
- **Rate limiting** — Too many login attempts

### Your Browser Succeeds Because
Your browser sends:
- Real User-Agent string
- Complete set of headers (Accept-Language, Accept-Encoding, etc.)
- Proper Referer headers on form POST
- Standard browser security headers
- Cookies and session tracking

### Why Scraper Failed Before
The scraper was sending:
- Minimal User-Agent
- Incomplete headers
- No Referer header on POST
- Missing security headers

---

## Solution Implemented

### 1. Enhanced Browser Headers

#### Added:
```python
"Accept-Language": "en-US,en;q=0.9,en;q=0.8",  # More realistic language preference
"Accept-Encoding": "gzip, deflate, br",         # Supports compression
"Connection": "keep-alive",                      # Keep-alive connection
"Upgrade-Insecure-Requests": "1",               # HTTPS preference
"Sec-Fetch-Dest": "document",                   # Security header
"Sec-Fetch-Mode": "navigate",                   # Security header
"Sec-Fetch-Site": "none",                       # Security header
```

These headers make the scraper look much more like a real Chrome browser.

### 2. Added Referer Header to Login POST

#### Before
```python
resp = await _request_with_retry(
    self._session,
    "POST",
    EVERSOURCE_LOGIN_URL,
    data=payload,
)
```

#### After
```python
post_headers = {"Referer": EVERSOURCE_LOGIN_URL}
resp = await _request_with_retry(
    self._session,
    "POST",
    EVERSOURCE_LOGIN_URL,
    data=payload,
    headers=post_headers,  # Added Referer header
)
```

Real browsers always send a Referer header showing where the form came from. This is expected by web servers.

### 3. Added Anti-Bot Detection in Logs

New error detection for:
- HTTP 429 (Rate Limited) — Too many login attempts
- HTTP 403 (Forbidden) — May be blocked by anti-bot
- Response content checking for: "cloudflare", "challenge", "bot", "verify", "javascript", "blocked"

---

## Why This Works

### How Real Browsers Work
1. Browser visits login page
2. Browser sees form with fields
3. Browser sends POST with:
   - All the form fields
   - User-Agent (real browser string)
   - Accept headers (what content I accept)
   - Referer (where the form came from)
   - Connection management headers
   - Security headers

### How Our Scraper Now Works
1. Scraper visits login page
2. Scraper extracts form fields
3. Scraper sends POST with:
   - ✅ All form fields (already done)
   - ✅ Real User-Agent (already done)
   - ✅ Accept headers (now enhanced)
   - ✅ Referer header (NEW)
   - ✅ Connection headers (NEW)
   - ✅ Security headers (NEW)

---

## Error Messages Now Detect

### HTTP 429 - Rate Limited
```
Eversource rate limited (HTTP 429). Too many login attempts.
Wait several hours before trying again.
```
**Meaning**: You've tried logging in too many times. Wait before retrying.

### HTTP 403 - Forbidden
```
Eversource forbidden (HTTP 403). You may be blocked by anti-bot measures.
Try again later, or contact Eversource support.
```
**Meaning**: Your IP or request pattern is blocked.

### HTTP 500+ With Anti-Bot Indicators
```
Eversource login may be blocked by anti-bot measures.
Try again later, or access eversource.com in your browser to verify.
Status=500, url=...
```
**Meaning**: Server error combined with anti-bot detection.

### Normal Login Failure (Credentials)
```
Eversource login validation uncertain: status=200, url=...
Credentials may be invalid, account may have 2FA enabled, or...
```
**Meaning**: Login issue not related to blocking.

---

## Testing the Fix

### Test 1: Verify Browser Headers
```python
# In debug logs, you should now see:
# Headers include: Accept-Language, Accept-Encoding, Connection, Sec-* headers
```

### Test 2: Verify Referer Header
```python
# In debug logs, you should see:
# Login POST response: status=X, final_url=..., sent Referer header
```

### Test 3: Check Error Messages
When you get an error, check if it mentions:
- Anti-bot measures
- Rate limiting (429)
- Forbidden (403)
- Or normal credential issues

---

## What To Do If Still Getting Blocked

### 1. Try Again Later
- Anti-bot systems have cooldown periods
- Wait 1-2 hours and retry
- Don't retry repeatedly (increases blocks)

### 2. Test in Browser
- Go to https://www.eversource.com/security/account/login
- Log in manually
- If browser login works, anti-bot was temporary
- If browser login also fails, credentials may be wrong

### 3. Check Your IP
- Some ISPs are blacklisted (if using shared IP)
- Try from a different network if possible
- Or contact Eversource about IP being blocked

### 4. Check Account Status
- Log in to Eversource portal
- Check account settings
- Look for security alerts or blocks
- Verify 2FA isn't enabled

### 5. Contact Eversource
- If persistently blocked, contact support
- Mention you're integrating with Home Assistant
- Ask if your account/IP is on a blocklist

---

## Browser Headers Explained

| Header | What It Means | Example |
|--------|--------------|---------|
| User-Agent | What browser/OS | Chrome on Windows 10 |
| Accept | File types I accept | HTML, XML, etc. |
| Accept-Language | Languages I prefer | en-US, en, etc. |
| Accept-Encoding | Compression I support | gzip, deflate, br |
| Connection | Connection management | keep-alive (persistent) |
| Referer | Where I came from | Login page URL |
| Sec-Fetch-Dest | What I'm fetching | document (page) |
| Sec-Fetch-Mode | How I'm fetching | navigate (normal page load) |
| Sec-Fetch-Site | Cross-site info | none (same site) |

These are **standard headers** sent by every browser. Websites expect them.

---

## Rate Limiting vs Blocking

### Rate Limiting (HTTP 429)
- **Cause**: Too many requests in short time
- **Fix**: Wait several hours, don't retry frequently
- **Normal**: Happens on most sites if you spam requests

### IP Blocking (HTTP 403)
- **Cause**: IP address on blocklist
- **Fix**: Wait, try from different IP, or contact support
- **Rare**: Usually happens after rate limiting

### Anti-Bot Detection (403, 500, etc.)
- **Cause**: Request doesn't look like real browser
- **Fix**: Enhanced headers (just implemented)
- **Common**: Many sites use Cloudflare or similar

---

## Prevention Tips

### Do:
✅ Wait 10-15 minutes between retries
✅ Use debug logging to diagnose
✅ Test manual login in browser
✅ Report issues with full logs
✅ Contact Eversource if blocked long-term

### Don't:
❌ Retry login 10+ times quickly
❌ Run multiple instances of scraper
❌ Change polling interval to very frequent
❌ Try different passwords repeatedly
❌ Use VPN/proxy without testing first

---

## Summary

**What Changed:**
- Added complete set of browser headers
- Added Referer header to login POST
- Better error detection for blocking

**Why It Helps:**
- Scraper now looks like real browser to Eversource
- Less likely to trigger anti-bot measures
- Better error messages if still blocked

**Next Step:**
- Try logging in again with the enhanced headers
- If still blocked, check logs for specific error
- Use troubleshooting guide based on error message

**Expected Result:**
- If it was a header-based block → Login now works
- If it's account-based block → Better error messages
- Either way → You'll know exactly what the problem is

---

## Technical Details

### Session & Cookie Handling
The `aiohttp.ClientSession` automatically:
- Maintains cookies across requests
- Handles redirects
- Persists headers

### Header Merging
- Default headers sent with every request
- POST-specific headers (like Referer) added as needed
- No header conflicts (POST headers override defaults if needed)

### Why Referer Matters
Web servers expect:
```
User visits page A → User fills form → User POSTs to page A
POST request includes "Referer: page A"
Server sees Referer matches POST destination → Legitimate
```

Without Referer:
```
POST from unknown origin → Server suspicious
May trigger anti-bot checks
```

---

## Files Modified

- **parsers/eversource_scraper.py**
  - Enhanced `_DEFAULT_HEADERS` with complete browser headers
  - Added Referer header to login POST
  - Enhanced error detection for 429, 403, anti-bot indicators
  - Better debug logging for anti-bot checks

All changes are backward compatible and don't affect other functionality.

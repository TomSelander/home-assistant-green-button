#!/usr/bin/env python3
"""
Inspect the Eversource login form structure to diagnose field names.
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup

EVERSOURCE_LOGIN_URL = "https://www.eversource.com/security/account/login"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


async def main():
    async with aiohttp.ClientSession(headers=_DEFAULT_HEADERS) as session:
        resp = await session.get(
            EVERSOURCE_LOGIN_URL,
            allow_redirects=True,
            timeout=aiohttp.ClientTimeout(total=30),
        )

        html = await resp.text()

        # Parse the HTML
        soup = BeautifulSoup(html, "html.parser")

        print("=" * 70)
        print("EVERSOURCE LOGIN FORM INSPECTION")
        print("=" * 70)
        print()

        # Find the form
        form = soup.find("form", attrs={"method": "post"}) or soup.find("form")
        if form:
            print(f"Form found: {form.get('id')} (method: {form.get('method')})")
            print(f"Form action: {form.get('action')}")
            print()

            # Find all input fields
            print("INPUT FIELDS:")
            print("-" * 70)
            for inp in form.find_all("input"):
                name = inp.get("name", "(no name)")
                field_type = inp.get("type", "text").lower()
                value = inp.get("value", "(empty)")[:50]
                field_id = inp.get("id", "(no id)")

                if field_type == "hidden":
                    print(f"  [HIDDEN] {name} = {value}")
                    print(f"           id: {field_id}")
                else:
                    print(f"  [{field_type.upper()}] {name}")
                    print(f"           id: {field_id}")
                    if field_type == "text":
                        print(f"           placeholder: {inp.get('placeholder', '(none)')}")
                    if field_type == "password":
                        print(f"           placeholder: {inp.get('placeholder', '(none)')}")
                print()
        else:
            print("No form found!")
            print()
            # Try to find any inputs outside a form
            print("All input fields on page:")
            for inp in soup.find_all("input"):
                print(f"  {inp.get('name', '(no name)')} - type: {inp.get('type', 'text')}")

        # Look for buttons
        print()
        print("BUTTONS:")
        print("-" * 70)
        for btn in form.find_all("button") if form else []:
            print(f"  {btn.get('name', '(no name)')} - {btn.get_text(strip=True)}")
        print()

        # Look for any JavaScript with login logic
        print("FORM ACTION INFO:")
        print("-" * 70)
        if form:
            action = form.get("action")
            method = form.get("method", "POST").upper()
            print(f"  Method: {method}")
            print(f"  Action: {action}")
            if not action or action.startswith("http"):
                print(f"  → Full URL: {action or EVERSOURCE_LOGIN_URL}")
            else:
                print(f"  → Full URL: https://www.eversource.com{action}")
        print()


if __name__ == "__main__":
    asyncio.run(main())

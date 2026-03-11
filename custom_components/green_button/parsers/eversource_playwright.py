"""Eversource web scraper using Playwright for browser automation.

This module uses Playwright to control a real browser, allowing it to:
- Execute JavaScript-based login forms (Okta OAuth)
- Handle modern anti-bot detection
- Extract usage history from dynamically loaded pages
- Work with any future Eversource page redesigns

RATE LIMITING & REQUEST EFFICIENCY:
    - Polling interval: 12 hours (configured via DEFAULT_SCAN_INTERVAL_HOURS)
    - Single browser session per poll
    - Timeout: 30 seconds per operation
    - Memory: Browser closed after each poll to avoid memory leaks
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page

logger = logging.getLogger(__name__)

# URLs
EVERSOURCE_LOGIN_URL = "https://www.eversource.com/security/account/login"
EVERSOURCE_USAGE_URL = "https://www.eversource.com/cg/customer/usagehistory"

# Timeouts
_LOGIN_TIMEOUT_MS = 60_000  # 60 seconds for login
_PAGE_LOAD_TIMEOUT_MS = 30_000  # 30 seconds for page load
_ELEMENT_TIMEOUT_MS = 10_000  # 10 seconds for element wait

# Pagination
_MAX_PAGINATION_PAGES = 50
_PAGINATION_REQUEST_DELAY_SECONDS = 1.0


class EversourcePlaywrightError(Exception):
    """Error raised when the Eversource Playwright scraper encounters a problem."""


class EversourcePlaywrightClient:
    """Async client for Eversource using Playwright browser automation.

    Uses a real browser to handle JavaScript-based login (Okta OAuth) and
    to extract data from dynamically loaded pages.
    """

    def __init__(
        self,
        username: str,
        password: str,
        browser: Browser | None = None,
    ) -> None:
        """Initialize with credentials and optional browser instance.

        Args:
            username: Eversource account username/email.
            password: Eversource account password.
            browser: Optional Playwright Browser instance.
                    If None, caller must provide one before async_login().
        """
        self._username = username
        self._password = password
        self._browser = browser
        self._page: Page | None = None
        self._logged_in = False

    async def async_login(self) -> bool:
        """Authenticate to Eversource using Playwright browser.

        Opens the login page, waits for it to load, enters credentials,
        and submits the login form. The browser handles all JavaScript
        execution and OAuth redirects automatically.

        Returns:
            True if login succeeded, False otherwise.
        """
        if not self._browser:
            logger.error("Browser instance not provided to async_login()")
            return False

        logger.info("Attempting Eversource login for user %s", self._username)

        try:
            # Create a new page/context for this login session
            self._page = await self._browser.new_page()

            # Set a reasonable timeout for all operations
            self._page.set_default_timeout(_PAGE_LOAD_TIMEOUT_MS)

            logger.debug("Created new browser page for login")

            # Step 1: Navigate to login page
            logger.debug("Navigating to login page: %s", EVERSOURCE_LOGIN_URL)
            try:
                await self._page.goto(
                    EVERSOURCE_LOGIN_URL,
                    wait_until="domcontentloaded",
                    timeout=_PAGE_LOAD_TIMEOUT_MS,
                )
            except Exception as e:
                logger.warning("Page load timeout or error (continuing anyway): %s", e)
                # Continue anyway - page may be partially loaded

            logger.debug("Login page loaded successfully")

            # Step 2: Wait for username field and enter credentials
            # Try multiple selectors since Eversource may update their HTML
            username_selectors = [
                "input[name='username']",
                "input[name='email']",
                "input[id*='username']",
                "input[id*='email']",
                "input[placeholder*='email' i]",
                "input[placeholder*='username' i]",
            ]

            username_field = None
            for selector in username_selectors:
                try:
                    if await self._page.query_selector(selector):
                        username_field = selector
                        logger.debug("Found username field: %s", selector)
                        break
                except Exception:
                    continue

            if not username_field:
                logger.error(
                    "Could not find username input field on Eversource login page. "
                    "The page structure may have changed."
                )
                return False

            # Enter username
            logger.debug("Entering username")
            await self._page.fill(username_field, self._username)

            # Step 3: Find and fill password field
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "input[id*='password']",
            ]

            password_field = None
            for selector in password_selectors:
                try:
                    if await self._page.query_selector(selector):
                        password_field = selector
                        logger.debug("Found password field: %s", selector)
                        break
                except Exception:
                    continue

            if not password_field:
                logger.error(
                    "Could not find password input field on Eversource login page. "
                    "The page structure may have changed."
                )
                return False

            # Enter password
            logger.debug("Entering password")
            await self._page.fill(password_field, self._password)

            # Step 4: Find and click login button
            login_button_selectors = [
                "button[type='submit']",
                "button:has-text('Sign In')",
                "button:has-text('Login')",
                "button:has-text('Log In')",
                "input[type='submit']",
                "[role='button']:has-text('Sign In')",
                "[role='button']:has-text('Login')",
            ]

            login_button = None
            for selector in login_button_selectors:
                try:
                    if await self._page.query_selector(selector):
                        login_button = selector
                        logger.debug("Found login button: %s", selector)
                        break
                except Exception:
                    continue

            if not login_button:
                logger.error(
                    "Could not find login button on Eversource login page. "
                    "The page structure may have changed."
                )
                return False

            # Click login button
            logger.debug("Clicking login button")
            await self._page.click(login_button)
            await self._page.wait_for_timeout(3000)  # Let form submission process

            # Step 5: Wait for login to complete
            # The page will redirect after successful login, or stay on login page if failed
            logger.debug("Waiting for login to complete (up to 60 seconds)")

            try:
                # Wait for navigation away from login page, or timeout
                await self._page.wait_for_url(
                    lambda url: "login" not in url.lower(),
                    timeout=_LOGIN_TIMEOUT_MS,
                )
                logger.info(
                    "Login succeeded - redirected to: %s",
                    self._page.url,
                )
            except asyncio.TimeoutError:
                logger.debug("Timeout waiting for redirect - checking current state")

            # Step 6: Handle 2FA prompt if present
            await self._page.wait_for_timeout(2000)  # Let page settle
            current_url = self._page.url.lower()

            if any(x in current_url for x in ["2fa", "2-fa", "verify", "challenge", "mfa"]):
                logger.debug("2FA prompt detected at URL: %s", self._page.url)
                logger.debug("Attempting to skip 2FA setup...")

                try:
                    # Try to find and click "Ask Me Again Later" button
                    buttons = await self._page.query_selector_all("button")
                    for btn in buttons:
                        text = await btn.text_content()
                        if text and "Ask Me Again Later" in text:
                            logger.debug("Found 'Ask Me Again Later' button - clicking")
                            await btn.click()
                            await self._page.wait_for_timeout(2000)
                            logger.debug("2FA skipped successfully")
                            break
                except Exception as err:
                    logger.warning("Error skipping 2FA: %s", err)
                    # Continue anyway - user may have 2FA disabled

            # Verify we're logged in by checking if we're still on login page
            current_url = self._page.url.lower()
            if "login" not in current_url:
                logger.info("Login successful - no longer on login page")
                self._logged_in = True
                return True

            # If we're still on login page after all attempts, login failed
            logger.warning(
                "Still on login page after login attempt - credentials likely invalid. URL: %s",
                self._page.url,
            )

            # Check for error messages
            page_content = await self._page.content()
            if "invalid" in page_content.lower() or "error" in page_content.lower():
                logger.warning("Error message detected on page - credentials may be wrong")

            return False

        except Exception as err:
            logger.exception("Unexpected error during Eversource login: %s", err)
            return False

    async def async_fetch_usage_history(self) -> str:
        """Fetch usage history page HTML after login.

        Returns:
            Raw HTML string of the usage history page.

        Raises:
            EversourcePlaywrightError: If not logged in or request fails.
        """
        if not self._logged_in or not self._page:
            raise EversourcePlaywrightError(
                "Must call async_login() successfully before fetching usage history"
            )

        logger.info("Fetching Eversource usage history page")

        try:
            await self._page.goto(
                EVERSOURCE_USAGE_URL,
                wait_until="domcontentloaded",
                timeout=_PAGE_LOAD_TIMEOUT_MS,
            )

            logger.debug("Usage history page loaded - waiting for table data to populate")

            # Wait for the usage table to appear with data
            try:
                await self._page.wait_for_selector(
                    "table#usageChartTable tbody tr",
                    timeout=_ELEMENT_TIMEOUT_MS
                )
                logger.debug("Usage table found with data rows")
            except Exception as e:
                logger.warning("Timeout waiting for table rows: %s (continuing anyway)", e)

            # Wait for page to settle
            await self._page.wait_for_timeout(2000)

            html = await self._page.content()
            logger.info("Fetched usage history page (%d characters)", len(html))
            return html

        except Exception as err:
            raise EversourcePlaywrightError(
                f"Failed to fetch usage history: {err}"
            ) from err

    async def async_get_full_usage_history(self) -> str:
        """Fetch usage history with full pagination handling.

        Uses Playwright to interact with "Show More" buttons and waits for
        the page to load additional data.

        Returns:
            Raw HTML string containing the full usage history table.
        """
        html = await self.async_fetch_usage_history()

        page = 0
        while page < _MAX_PAGINATION_PAGES:
            # Check if there's a "Show More" button
            show_more_selector = None
            try:
                # Try different "Show More" button selectors
                selectors = [
                    "button:has-text('Show More')",
                    "a:has-text('Show More')",
                    "[class*='show-more' i]",
                    "[id*='show-more' i]",
                ]

                for selector in selectors:
                    if await self._page.query_selector(selector):
                        show_more_selector = selector
                        logger.debug("Found Show More button: %s", selector)
                        break

                if not show_more_selector:
                    logger.debug("No further Show More button found")
                    break

                # Click the Show More button
                logger.info("Found Show More button (page %d), clicking", page + 1)
                await self._page.click(show_more_selector)

                # Rate limiting: wait before next page
                await asyncio.sleep(_PAGINATION_REQUEST_DELAY_SECONDS)

                # Wait for new data to load
                await self._page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT_MS)

                # Get updated HTML
                html = await self._page.content()
                page += 1

            except Exception as err:
                logger.warning("Error during pagination (page %d): %s", page + 1, err)
                break

        if page >= _MAX_PAGINATION_PAGES:
            logger.warning("Reached maximum pagination limit (%d pages)", _MAX_PAGINATION_PAGES)

        return html

    async def async_close(self) -> None:
        """Clean up browser page."""
        if self._page and not self._page.is_closed():
            await self._page.close()
            logger.debug("Closed Eversource browser page")


# ============================================================================
# HTML parsing (same as form-based scraper)
# ============================================================================


def parse_usage_table(html: str) -> list[dict]:
    """Parse the Eversource usage history HTML table.

    Extracts rows from table#usageChartTable and parses each column into
    structured data.

    Args:
        html: Raw HTML string containing the usage history table.

    Returns:
        List of dicts, each containing usage data.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", attrs={"id": "usageChartTable"})

    if not table:
        logger.warning("Could not find usage history table in HTML")
        return []

    rows = []
    for tr in table.find_all("tr")[1:]:  # Skip header row
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        try:
            read_date_str = tds[0].get_text(strip=True)
            read_date = datetime.datetime.strptime(read_date_str, "%m/%d/%Y").date()

            usage_kwh = float(tds[1].get_text(strip=True).replace(",", ""))
            num_days = int(tds[2].get_text(strip=True))
            usage_per_day = float(tds[3].get_text(strip=True))
            cost_per_day = float(tds[4].get_text(strip=True).replace("$", ""))
            total_charge = float(tds[5].get_text(strip=True).replace("$", ""))

            rows.append({
                "read_date": read_date,
                "usage_kwh": usage_kwh,
                "num_days": num_days,
                "usage_per_day": usage_per_day,
                "cost_per_day": cost_per_day,
                "total_charge": total_charge,
            })
        except (ValueError, IndexError, AttributeError) as err:
            logger.debug("Error parsing usage row: %s", err)
            continue

    logger.info("Parsed %d usage history rows", len(rows))
    return rows

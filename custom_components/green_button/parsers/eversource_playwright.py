"""Eversource web scraper using pyppeteer for browser automation.

This module uses pyppeteer (pure Python Puppeteer) to control a headless browser, allowing it to:
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
    from pyppeteer.browser import Browser
    from pyppeteer.page import Page

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
        """Authenticate to Eversource using pyppeteer browser.

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
            pages = await self._browser.pages()
            if pages:
                self._page = pages[0]
                await self._page.goto("about:blank")  # Clear page
            else:
                self._page = await self._browser.newPage()

            logger.debug("Created new browser page for login")

            # Step 1: Navigate to login page
            logger.debug("Navigating to login page: %s", EVERSOURCE_LOGIN_URL)
            try:
                await self._page.goto(
                    EVERSOURCE_LOGIN_URL,
                    waitUntil="domcontentloaded",
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
            ]

            username_field = None
            for selector in username_selectors:
                try:
                    element = await self._page.querySelector(selector)
                    if element:
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
            await self._page.type(username_field, self._username)

            # Step 3: Find and fill password field
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "input[id*='password']",
            ]

            password_field = None
            for selector in password_selectors:
                try:
                    element = await self._page.querySelector(selector)
                    if element:
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
            await self._page.type(password_field, self._password)

            # Step 4: Find and click login button
            login_button_selectors = [
                "button[type='submit']",
                "input[type='submit']",
            ]

            login_button = None
            for selector in login_button_selectors:
                try:
                    element = await self._page.querySelector(selector)
                    if element:
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
            await asyncio.sleep(3)  # Let form submission process

            # Step 5: Wait for login to complete (poll for URL change)
            logger.debug("Waiting for login to complete (up to 60 seconds)")
            start_time = asyncio.get_event_loop().time()
            while asyncio.get_event_loop().time() - start_time < _LOGIN_TIMEOUT_MS / 1000:
                current_url = self._page.url.lower()
                if "login" not in current_url:
                    logger.info("Login succeeded - redirected to: %s", self._page.url)
                    break
                await asyncio.sleep(1)

            # Step 6: Handle 2FA prompt if present
            await asyncio.sleep(2)  # Let page settle
            current_url = self._page.url.lower()

            if any(x in current_url for x in ["2fa", "2-fa", "verify", "challenge", "mfa"]):
                logger.debug("2FA prompt detected at URL: %s", self._page.url)
                logger.debug("Attempting to skip 2FA setup...")

                try:
                    # Try to find and click "Ask Me Again Later" button
                    buttons = await self._page.querySelectorAll("button")
                    for btn in buttons:
                        try:
                            text = await self._page.evaluate("btn => btn.textContent", btn)
                            if text and "Ask Me Again Later" in text:
                                logger.debug("Found 'Ask Me Again Later' button - clicking")
                                await btn.click()
                                await asyncio.sleep(2)
                                logger.debug("2FA skipped successfully")
                                break
                        except Exception:
                            continue
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
                waitUntil="domcontentloaded",
                timeout=_PAGE_LOAD_TIMEOUT_MS,
            )

            logger.debug("Usage history page loaded - waiting for table data to populate")

            # Wait for the usage table to appear with data
            try:
                await self._page.waitForSelector(
                    "table#usageChartTable tbody tr",
                    timeout=_ELEMENT_TIMEOUT_MS
                )
                logger.debug("Usage table found with data rows")
            except Exception as e:
                logger.warning("Timeout waiting for table rows: %s (continuing anyway)", e)

            # Wait for page to settle
            await asyncio.sleep(2)

            html = await self._page.content()
            logger.info("Fetched usage history page (%d characters)", len(html))
            return html

        except Exception as err:
            raise EversourcePlaywrightError(
                f"Failed to fetch usage history: {err}"
            ) from err

    async def async_get_full_usage_history(self) -> str:
        """Fetch usage history with full pagination handling.

        Uses pyppeteer to interact with "Show More" buttons and waits for
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
                    "button",  # Simple button selector since pyppeteer doesn't support :has-text()
                ]

                for selector in selectors:
                    elements = await self._page.querySelectorAll(selector)
                    for elem in elements:
                        try:
                            text = await self._page.evaluate("elem => elem.textContent", elem)
                            if text and "Show More" in text:
                                show_more_selector = selector
                                logger.debug("Found Show More button")
                                break
                        except Exception:
                            continue
                    if show_more_selector:
                        break

                if not show_more_selector:
                    logger.debug("No further Show More button found")
                    break

                # Click the Show More button
                logger.info("Found Show More button (page %d), clicking", page + 1)
                show_more_btn = await self._page.querySelector("button")
                if show_more_btn:
                    await show_more_btn.click()

                # Rate limiting: wait before next page
                await asyncio.sleep(_PAGINATION_REQUEST_DELAY_SECONDS)

                # Wait for new data to load
                await asyncio.sleep(2)

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
        if self._page:
            try:
                await self._page.close()
                logger.debug("Closed Eversource browser page")
            except Exception as err:
                logger.debug("Error closing page: %s", err)


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


def to_usage_points(scraped_data: list[dict]) -> list[Any]:
    """Convert scraped Eversource usage data to Home Assistant model objects.

    Creates a single UsagePoint containing a single MeterReading with
    IntervalBlocks derived from each row of scraped data.

    Args:
        scraped_data: List of dicts from parse_usage_table().

    Returns:
        List containing a single UsagePoint with the scraped data.
    """
    from . import model
    from homeassistant.components import sensor  # type: ignore[import-untyped]

    if not scraped_data:
        logger.warning("No scraped data to convert")
        return []

    interval_blocks: list[Any] = []

    for idx, row in enumerate(scraped_data):
        read_date: datetime.date = row["read_date"]
        num_days: int = row.get("num_days", 0) or 0
        usage_kwh: float = row.get("usage_kwh", 0.0) or 0.0
        total_charge: float = row.get("total_charge", 0.0) or 0.0

        if num_days <= 0:
            logger.warning(
                "Skipping row %d: invalid num_days=%d", idx, num_days
            )
            continue

        # Calculate billing period start from read_date and num_days
        period_duration = datetime.timedelta(days=num_days)
        # Convert date to datetime at midnight
        read_datetime = datetime.datetime.combine(read_date, datetime.time.min)
        period_start = read_datetime - period_duration

        # Determine interval length in seconds for this billing period
        interval_length = num_days * 86400

        # Create a ReadingType for this specific interval
        reading_type = model.ReadingType(
            id=f"eversource_reading_type_{idx}",
            commodity=0,  # Electricity
            currency="USD",
            power_of_ten_multiplier=0,
            unit_of_measurement="Wh",
            interval_length=interval_length,
        )

        # Convert kWh to Wh for value, dollars to cents for cost
        value_wh = int(usage_kwh * 1000)
        cost_cents = int(total_charge * 100)

        interval_reading = model.IntervalReading(
            reading_type=reading_type,
            cost=cost_cents,
            start=period_start,
            duration=period_duration,
            value=value_wh,
        )

        interval_block = model.IntervalBlock(
            id=f"eversource_block_{idx}",
            reading_type=reading_type,
            start=period_start,
            duration=period_duration,
            interval_readings=[interval_reading],
        )

        interval_blocks.append(interval_block)

    if not interval_blocks:
        logger.warning("No valid interval blocks created from scraped data")
        return []

    # Use the reading type from the first block for the meter reading
    primary_reading_type = interval_blocks[0].reading_type

    meter_reading = model.MeterReading(
        id="eversource_meter",
        reading_type=primary_reading_type,
        interval_blocks=interval_blocks,
    )

    usage_point = model.UsagePoint(
        id="eversource_usage_point",
        sensor_device_class=sensor.SensorDeviceClass.ENERGY,
        meter_readings=[meter_reading],
    )

    logger.info(
        "Created UsagePoint with %d interval blocks from scraped data",
        len(interval_blocks),
    )

    return [usage_point]

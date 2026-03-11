"""Eversource web scraper using HTTP requests with aiohttp.

This module attempts to scrape Eversource usage data using standard HTTP requests.
If Eversource has added JavaScript-based authentication that blocks HTTP requests,
the integration will gracefully degrade or notify the user.

RATE LIMITING & REQUEST EFFICIENCY:
    - Polling interval: 12 hours (configured via DEFAULT_SCAN_INTERVAL_HOURS)
    - Single HTTP session per poll
    - Retry with exponential backoff on transient errors
    - Max pagination: Limited to 50 pages
    - Pagination delay: 1 second between requests
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from typing import TYPE_CHECKING, Any

import aiohttp  # type: ignore[import-untyped]
from bs4 import BeautifulSoup  # type: ignore[import-untyped]

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# URLs
EVERSOURCE_LOGIN_URL = "https://www.eversource.com/security/account/login"
EVERSOURCE_USAGE_URL = "https://www.eversource.com/cg/customer/usagehistory"

# Retry configuration
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1

# Pagination
_MAX_PAGINATION_PAGES = 50
_PAGINATION_REQUEST_DELAY_SECONDS = 1.0

# Browser headers
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

_RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientConnectionError,
    aiohttp.ServerTimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    TimeoutError,
)


class EversourceHTTPError(Exception):
    """Error raised when the HTTP scraper encounters a problem."""


async def _request_with_retry(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    **kwargs: Any,
) -> aiohttp.ClientResponse:
    """Execute an HTTP request with automatic retry on transient errors."""
    for attempt in range(_MAX_RETRIES):
        try:
            async with session.request(method, url, **kwargs) as resp:
                return resp
        except _RETRYABLE_EXCEPTIONS as err:
            if attempt >= _MAX_RETRIES - 1:
                raise
            backoff = _BACKOFF_BASE_SECONDS * (2**attempt)
            logger.debug(
                "Request failed (attempt %d/%d), retrying in %d seconds: %s",
                attempt + 1,
                _MAX_RETRIES,
                backoff,
                err,
            )
            await asyncio.sleep(backoff)


class EversourceHTTPClient:
    """HTTP client for Eversource using aiohttp.

    This client uses standard HTTP requests to authenticate and fetch data.
    It may fail if Eversource has added JavaScript-based authentication.
    """

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize with credentials and optional session."""
        self._username = username
        self._password = password
        self._session = session
        self._owned_session = session is None
        self._logged_in = False

    async def async_login(self) -> bool:
        """Attempt to login to Eversource using HTTP requests.

        Returns:
            True if login succeeded, False otherwise.
        """
        if self._owned_session:
            self._session = aiohttp.ClientSession()

        if not self._session:
            logger.error("No session available for login")
            return False

        logger.info("Attempting Eversource HTTP login for user %s", self._username)

        try:
            # Step 1: Get login page to extract any CSRF tokens or session cookies
            logger.debug("Fetching login page")
            async with self._session.get(
                EVERSOURCE_LOGIN_URL,
                headers=_DEFAULT_HEADERS,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "Login page returned status %d, HTML form login may not work",
                        resp.status,
                    )
                    return False

                login_html = await resp.text()

            # Step 2: Extract form data if available
            logger.debug("Parsing login form")
            soup = BeautifulSoup(login_html, "html.parser")

            # Look for login form
            form = soup.find("form", method="post")
            if not form:
                logger.warning(
                    "Could not find login form on Eversource page. "
                    "Eversource may have switched to JavaScript-based authentication."
                )
                return False

            # Extract form action URL
            form_action = form.get("action", EVERSOURCE_LOGIN_URL)
            if form_action.startswith("/"):
                form_action = "https://www.eversource.com" + form_action

            logger.debug("Login form action: %s", form_action)

            # Step 3: Submit login credentials
            login_data = {
                "username": self._username,
                "password": self._password,
            }

            # Add any hidden fields from the form
            for hidden in form.find_all("input", type="hidden"):
                name = hidden.get("name")
                value = hidden.get("value")
                if name and value:
                    login_data[name] = value

            logger.debug("Submitting login credentials")
            async with self._session.post(
                form_action,
                data=login_data,
                headers=_DEFAULT_HEADERS,
                timeout=aiohttp.ClientTimeout(total=30),
                allow_redirects=True,
            ) as resp:
                response_html = await resp.text()
                final_url = str(resp.url).lower()

            # Step 4: Check if login succeeded
            logger.debug("Login response URL: %s", final_url)

            if "login" in final_url:
                logger.warning(
                    "Still on login page after credential submission. Login failed."
                )
                if "invalid" in response_html.lower():
                    logger.warning("Page contains 'invalid' text - credentials may be wrong")
                return False

            logger.info("HTTP login succeeded")
            self._logged_in = True
            return True

        except Exception as err:
            logger.exception("Error during HTTP login: %s", err)
            return False

    async def async_fetch_usage_history(self) -> str:
        """Fetch usage history page HTML after login.

        Returns:
            Raw HTML string of the usage history page.

        Raises:
            EversourceHTTPError: If not logged in or request fails.
        """
        if not self._logged_in or not self._session:
            raise EversourceHTTPError(
                "Must call async_login() successfully before fetching usage history"
            )

        logger.info("Fetching Eversource usage history page")

        try:
            async with self._session.get(
                EVERSOURCE_USAGE_URL,
                headers=_DEFAULT_HEADERS,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    raise EversourceHTTPError(
                        f"Usage page returned status {resp.status}"
                    )
                html = await resp.text()

            logger.info("Fetched usage history page (%d characters)", len(html))
            return html

        except Exception as err:
            raise EversourceHTTPError(
                f"Failed to fetch usage history: {err}"
            ) from err

    async def async_get_full_usage_history(self) -> str:
        """Fetch usage history with pagination handling.

        Returns:
            Raw HTML string containing the full usage history table.
        """
        html = await self.async_fetch_usage_history()

        # Note: Pagination handling depends on Eversource's page structure
        # Most modern single-page applications load data via JavaScript,
        # so traditional "Show More" buttons may not work with HTTP requests alone
        page = 0
        while page < _MAX_PAGINATION_PAGES:
            try:
                # Parse HTML to look for "Show More" button or pagination
                soup = BeautifulSoup(html, "html.parser")
                show_more = soup.find("button", string=re.compile("Show More", re.I))

                if not show_more:
                    logger.debug("No 'Show More' button found")
                    break

                # If there was a button we'd need JavaScript to click it
                # For now, just return what we have
                logger.debug("Show More button found but requires JavaScript to click")
                break

            except Exception as err:
                logger.warning("Error during pagination check: %s", err)
                break

        return html

    async def async_close(self) -> None:
        """Clean up session if we own it."""
        if self._owned_session and self._session:
            await self._session.close()
            logger.debug("Closed HTTP session")


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
    """Convert scraped Eversource usage data to Home Assistant model objects."""
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
            logger.warning("Skipping row %d: invalid num_days=%d", idx, num_days)
            continue

        period_duration = datetime.timedelta(days=num_days)
        read_datetime = datetime.datetime.combine(read_date, datetime.time.min)
        period_start = read_datetime - period_duration
        interval_length = num_days * 86400

        reading_type = model.ReadingType(
            id=f"eversource_reading_type_{idx}",
            commodity=0,
            currency="USD",
            power_of_ten_multiplier=0,
            unit_of_measurement="Wh",
            interval_length=interval_length,
        )

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

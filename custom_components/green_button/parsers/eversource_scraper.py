"""Eversource web scraper for fetching electricity usage data.

Authenticates to Eversource's web portal, fetches the usage history page,
parses the HTML table, and converts the data into Home Assistant model objects.

RATE LIMITING & REQUEST EFFICIENCY:
    - Polling interval: 12 hours (configured via DEFAULT_SCAN_INTERVAL_HOURS).
      This minimizes unnecessary requests to the Eversource server.
    - Single login per poll: One authentication attempt per coordinator update.
    - Pagination delays: 1-second delay between "Show More" requests to avoid
      overwhelming the server with rapid requests.
    - Max pagination: Limited to 50 pages to prevent runaway loops.
    - Retry backoff: Failed requests use exponential backoff (1s, 2s, 4s) rather
      than immediate retries, reducing server load on network issues.
    - No connection pooling or request caching across polls: Each poll creates
      a fresh client, which is simple and avoids stale session issues.

Session lifecycle:
    - EversourceClient creates (or accepts) an aiohttp.ClientSession.
    - Call async_login() to authenticate. The session retains cookies.
    - Call async_get_full_usage_history() to fetch and paginate data.
    - Call async_close() when finished to release the session.
    - If a session expires between coordinator polls, the next
      coordinator.async_refresh() creates a *new* EversourceClient that
      performs a fresh login -- no manual re-authentication is needed.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import re
from typing import TYPE_CHECKING, Any

import aiohttp  # type: ignore[import-untyped]
from bs4 import BeautifulSoup  # type: ignore[import-untyped]
from homeassistant.components import sensor  # type: ignore[import-untyped]

if TYPE_CHECKING:
    pass

from .. import model
from ..const import EVERSOURCE_LOGIN_URL, EVERSOURCE_USAGE_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1  # exponential: 1s, 2s, 4s

# Maximum number of "Show More" pagination iterations to prevent infinite loops
_MAX_PAGINATION_PAGES = 50

# Rate limiting: delay (seconds) between pagination requests to avoid overwhelming Eversource
_PAGINATION_REQUEST_DELAY_SECONDS = 1.0

# Common headers to mimic a real browser session
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Transient errors that warrant a retry
_RETRYABLE_EXCEPTIONS = (
    aiohttp.ClientConnectionError,
    aiohttp.ServerTimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    TimeoutError,
)


class EversourceScraperError(Exception):
    """Error raised when the Eversource scraper encounters a problem."""


async def _request_with_retry(
    session: aiohttp.ClientSession,
    method: str,
    url: str,
    **kwargs: Any,
) -> aiohttp.ClientResponse:
    """Execute an HTTP request with automatic retry on transient errors.

    Retries up to ``_MAX_RETRIES`` times using exponential back-off
    (1 s, 2 s, 4 s) for connection and timeout errors.  The caller is
    responsible for closing the response (or using ``async with``).

    RATE LIMITING STRATEGY:
    - Initial login: single attempt (no pagination, no multiple requests)
    - Usage history fetch: single request
    - Pagination pages: 1-second delay between requests to avoid overwhelming the server
    - Transient errors: exponential backoff (1s, 2s, 4s) with logging
    - Max pagination pages capped at 50 to prevent runaway loops

    Args:
        session: The aiohttp session to use.
        method: HTTP method (``"GET"`` or ``"POST"``).
        url: Target URL.
        **kwargs: Forwarded to ``session.request()``.

    Returns:
        The :class:`aiohttp.ClientResponse` on success.

    Raises:
        The original exception after all retries are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = await session.request(method, url, **kwargs)
            return resp
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                backoff_delay = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    "Request failed (attempt %d/%d): %s. Retrying in %0.1f seconds.",
                    attempt + 1,
                    _MAX_RETRIES,
                    type(exc).__name__,
                    backoff_delay,
                )
                await asyncio.sleep(backoff_delay)
            delay = _BACKOFF_BASE_SECONDS * (2 ** attempt)
            logger.warning(
                "Transient error on %s %s (attempt %d/%d): %s -- retrying in %ds",
                method,
                url,
                attempt + 1,
                _MAX_RETRIES,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    # All retries exhausted -- re-raise the last exception
    assert last_exc is not None  # noqa: S101
    raise last_exc


class EversourceClient:
    """Async client for interacting with the Eversource web portal.

    The client keeps the underlying :class:`aiohttp.ClientSession` alive
    between ``async_login`` and data-fetch calls so that authentication
    cookies persist.  When the caller is done it **must** call
    ``async_close`` (or use the client as an async context manager) to
    release network resources.

    If an existing session is passed in, the client will *not* close it
    on ``async_close`` -- the caller retains ownership.
    """

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize with credentials and optional session.

        Args:
            username: Eversource account username/email.
            password: Eversource account password.
            session: Optional aiohttp session to reuse.  If ``None`` a new
                session is created internally and will be closed by
                ``async_close``.
        """
        self._username = username
        self._password = password
        self._owns_session = session is None
        self._session = session or aiohttp.ClientSession(headers=_DEFAULT_HEADERS)
        self._logged_in = False

    async def async_login(self) -> bool:
        """Authenticate to Eversource by submitting the login form.

        Gets the login page, extracts hidden/CSRF fields, POSTs credentials,
        and verifies the login succeeded by checking the response.

        Returns:
            True if login succeeded, False otherwise.
        """
        logger.info("Attempting Eversource login for user %s", self._username)

        try:
            # Step 1: GET the login page to extract CSRF tokens and hidden fields
            resp = await _request_with_retry(
                self._session,
                "GET",
                EVERSOURCE_LOGIN_URL,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            async with resp:
                if resp.status != 200:
                    logger.error(
                        "Failed to load login page, status=%d", resp.status
                    )
                    return False
                login_html = await resp.text()

            # Step 2: Parse hidden fields from the login form
            soup = BeautifulSoup(login_html, "html.parser")
            form = soup.find("form", attrs={"method": re.compile(r"post", re.IGNORECASE)})
            if form is None:
                form = soup  # Fall back to searching the whole page

            hidden_fields = _extract_hidden_fields(form)
            logger.debug(
                "Extracted %d hidden fields from login form", len(hidden_fields)
            )

            # Step 3: Build login payload
            payload = {**hidden_fields}
            # Try common field names for username/password
            username_field = _find_field_name(
                soup, ["Username", "Email", "username", "email", "UserName"]
            )
            password_field = _find_field_name(
                soup, ["Password", "password", "passwd"]
            )

            payload[username_field or "Username"] = self._username
            payload[password_field or "Password"] = self._password

            # Step 4: POST the login form (with retry)
            resp = await _request_with_retry(
                self._session,
                "POST",
                EVERSOURCE_LOGIN_URL,
                data=payload,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            async with resp:
                response_text = await resp.text()

                # Check for login success indicators
                if resp.status == 200 and "sign out" in response_text.lower():
                    logger.info("Eversource login succeeded")
                    self._logged_in = True
                    return True

                if resp.status == 200 and "dashboard" in str(resp.url).lower():
                    logger.info("Eversource login succeeded (redirected to dashboard)")
                    self._logged_in = True
                    return True

                # If we followed a redirect chain and ended up on a non-login page
                if resp.status == 200 and "login" not in str(resp.url).lower():
                    logger.info(
                        "Eversource login likely succeeded (redirected away from login)"
                    )
                    self._logged_in = True
                    return True

                logger.error(
                    "Eversource login failed, final URL=%s, status=%d",
                    resp.url,
                    resp.status,
                )
                return False

        except aiohttp.ClientError as err:
            logger.error("Network error during Eversource login: %s", err)
            return False
        except Exception as err:
            logger.exception("Unexpected error during Eversource login: %s", err)
            return False

    async def async_fetch_usage_history(self) -> str:
        """Fetch the usage history page HTML after login.

        Returns:
            Raw HTML string of the usage history page.

        Raises:
            EversourceScraperError: If not logged in or request fails.
        """
        if not self._logged_in:
            raise EversourceScraperError(
                "Must call async_login() successfully before fetching usage history"
            )

        logger.info("Fetching Eversource usage history page")
        try:
            resp = await _request_with_retry(
                self._session,
                "GET",
                EVERSOURCE_USAGE_URL,
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            async with resp:
                if resp.status != 200:
                    raise EversourceScraperError(
                        f"Failed to fetch usage history, status={resp.status}"
                    )
                html = await resp.text()
                logger.info(
                    "Fetched usage history page (%d characters)", len(html)
                )
                return html
        except _RETRYABLE_EXCEPTIONS as err:
            raise EversourceScraperError(
                f"Network error fetching usage history: {err}"
            ) from err
        except aiohttp.ClientError as err:
            raise EversourceScraperError(
                f"Network error fetching usage history: {err}"
            ) from err

    async def async_get_full_usage_history(self) -> str:
        """Fetch usage history with full pagination handling.

        After loading the initial page this method inspects the HTML for
        a "Show More" control.  Three discovery strategies are attempted:

        1. An ``<a>`` or ``<button>`` whose visible text matches
           "Show More" (case-insensitive).
        2. Any element with a ``data-action`` attribute containing
           "more", "load", or "next".
        3. An ``onclick`` handler whose body contains a URL path
           (heuristic regex extraction).

        If a URL is found it is called as an AJAX GET (with the
        ``X-Requested-With: XMLHttpRequest`` header).  The response
        body -- which may be a full HTML fragment or a JSON payload
        containing an ``html`` key -- is appended to the accumulated
        HTML.  The loop continues up to ``_MAX_PAGINATION_PAGES`` times
        or until no further "Show More" control is detected.

        Returns:
            Raw HTML string containing the full usage history table.
        """
        html = await self.async_fetch_usage_history()

        page = 0
        while page < _MAX_PAGINATION_PAGES:
            ajax_url = self._detect_show_more_url(html)
            if ajax_url is None:
                logger.debug(
                    "No further 'Show More' pagination detected (fetched %d extra pages)",
                    page,
                )
                break

            logger.info(
                "Found 'Show More' link (page %d), fetching from %s",
                page + 1,
                ajax_url,
            )
            # Rate limiting: delay before requesting next page to avoid overwhelming server
            await asyncio.sleep(_PAGINATION_REQUEST_DELAY_SECONDS)
            extra_html = await self._fetch_pagination_page(ajax_url)
            if not extra_html:
                # Empty or failed response -- stop paginating
                logger.info(
                    "Pagination stopped: empty response on page %d", page + 1
                )
                break

            html = html + extra_html
            page += 1

        if page >= _MAX_PAGINATION_PAGES:
            logger.warning(
                "Reached maximum pagination limit (%d pages)", _MAX_PAGINATION_PAGES
            )

        return html

    # ------------------------------------------------------------------
    # Pagination helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_show_more_url(html: str) -> str | None:
        """Inspect *html* for a "Show More" control and return its URL.

        Returns ``None`` when no actionable URL is found.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: <a> or <button> with visible "Show More" text
        show_more = soup.find(
            "a", string=re.compile(r"show\s*more", re.IGNORECASE)
        ) or soup.find(
            "button", string=re.compile(r"show\s*more", re.IGNORECASE)
        )

        # Strategy 2: element with data-action containing "more/load/next"
        if show_more is None:
            show_more = soup.find(
                attrs={"data-action": re.compile(r"more|load|next", re.IGNORECASE)}
            )

        if show_more is not None:
            # Try href first, then data-url
            url = show_more.get("href") or show_more.get("data-url")
            if url and url != "#":
                return _resolve_url(url)

            # Strategy 3: try to extract URL from an onclick handler
            onclick = show_more.get("onclick", "")
            if onclick:
                extracted = _extract_url_from_onclick(onclick)
                if extracted:
                    return _resolve_url(extracted)

            logger.debug("'Show More' element found but no usable URL")
            return None

        # No element found at all
        return None

    async def _fetch_pagination_page(self, url: str) -> str:
        """Fetch a single AJAX pagination page.

        Returns the HTML fragment to append, or an empty string on
        failure (so pagination can stop gracefully).
        """
        try:
            resp = await _request_with_retry(
                self._session,
                "GET",
                url,
                headers={"X-Requested-With": "XMLHttpRequest"},
                allow_redirects=True,
                timeout=aiohttp.ClientTimeout(total=30),
            )
            async with resp:
                if resp.status != 200:
                    logger.warning(
                        "Failed to fetch pagination page, status=%d", resp.status
                    )
                    return ""
                body = await resp.text()
                logger.info(
                    "Fetched additional usage data (%d characters)", len(body)
                )
                # Some endpoints return JSON with an "html" key
                if body.lstrip().startswith("{"):
                    import json  # noqa: PLC0415

                    try:
                        data = json.loads(body)
                        return str(data.get("html", ""))
                    except (json.JSONDecodeError, AttributeError):
                        pass
                return body
        except aiohttp.ClientError as err:
            logger.warning("Network error fetching pagination page: %s", err)
            return ""

    async def async_close(self) -> None:
        """Clean up the HTTP session if we created it."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Closed Eversource HTTP session")


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def _resolve_url(url: str) -> str:
    """Resolve a possibly-relative URL to an absolute Eversource URL."""
    if url.startswith("/"):
        return f"https://www.eversource.com{url}"
    return url


def _extract_url_from_onclick(onclick: str) -> str | None:
    """Try to pull a URL path out of a JavaScript onclick handler.

    Looks for quoted strings that start with ``/`` or ``http``.

    Returns:
        The first URL-like string found, or ``None``.
    """
    match = re.search(r"""['"]((https?://[^'"]+)|(/[^'"]+))['"]""", onclick)
    if match:
        return match.group(1)
    return None


# ---------------------------------------------------------------------------
# Form helpers
# ---------------------------------------------------------------------------


def _extract_hidden_fields(form_element: Any) -> dict[str, str]:
    """Extract all hidden input fields from a form element.

    Args:
        form_element: A BeautifulSoup element (form or page).

    Returns:
        Dictionary of field name to value.
    """
    fields: dict[str, str] = {}
    for hidden_input in form_element.find_all("input", attrs={"type": "hidden"}):
        name = hidden_input.get("name")
        value = hidden_input.get("value", "")
        if name:
            fields[name] = value
    return fields


def _find_field_name(soup: Any, candidates: list[str]) -> str | None:
    """Find the actual field name used in the login form.

    Searches for input elements whose name or id matches one of the candidates.

    Args:
        soup: BeautifulSoup parsed page.
        candidates: List of possible field names to search for.

    Returns:
        The matched field name, or None if no match found.
    """
    for candidate in candidates:
        inp = soup.find("input", attrs={"name": candidate})
        if inp is not None:
            return candidate
        inp = soup.find("input", attrs={"id": candidate})
        if inp is not None:
            return inp.get("name", candidate)
    return None


# ---------------------------------------------------------------------------
# HTML table parsing
# ---------------------------------------------------------------------------


def parse_usage_table(html: str) -> list[dict]:
    """Parse the Eversource usage history HTML table.

    Extracts rows from table#usageChartTable and parses each column into
    structured data.

    Args:
        html: Raw HTML string containing the usage history table.

    Returns:
        List of dicts, each containing:
            - read_date: datetime.datetime
            - usage_kwh: float
            - num_days: int
            - usage_per_day: float
            - cost_per_day: float
            - total_charge: float
            - avg_temp: float | None

    Raises:
        EversourceScraperError: If the table cannot be found.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="usageChartTable")

    if table is None:
        # Try alternative selectors
        table = soup.find("table", class_=re.compile(r"usage", re.IGNORECASE))

    if table is None:
        logger.warning("Could not find usage table in HTML (len=%d)", len(html))
        raise EversourceScraperError(
            "Could not find usageChartTable in the page HTML"
        )

    rows: list[dict] = []
    tbody = table.find("tbody")
    tr_elements = (tbody or table).find_all("tr")

    logger.info("Found %d table rows to parse", len(tr_elements))

    for row_idx, tr in enumerate(tr_elements):
        cells = tr.find_all("td")
        if not cells:
            # Skip header rows or empty rows
            continue

        try:
            row_data = _parse_table_row(cells)
            rows.append(row_data)
        except (ValueError, IndexError) as err:
            logger.warning(
                "Skipping row %d due to parse error: %s", row_idx, err
            )
            continue

    logger.info("Successfully parsed %d usage rows", len(rows))
    return rows


def _parse_table_row(cells: list) -> dict:
    """Parse a single table row's cells into a dictionary.

    Expected column order:
        0: Read Date
        1: Usage (kWh)
        2: Number of Days
        3: Usage Per Day
        4: Cost Per Day
        5: Total Charge
        6: Avg Temp (optional)

    Args:
        cells: List of BeautifulSoup <td> elements.

    Returns:
        Dictionary with parsed values.

    Raises:
        ValueError: If required fields cannot be parsed.
        IndexError: If not enough columns.
    """
    if len(cells) < 6:
        raise ValueError(f"Expected at least 6 columns, got {len(cells)}")

    read_date_str = cells[0].get_text(strip=True)
    usage_kwh_str = cells[1].get_text(strip=True)
    num_days_str = cells[2].get_text(strip=True)
    usage_per_day_str = cells[3].get_text(strip=True)
    cost_per_day_str = cells[4].get_text(strip=True)
    total_charge_str = cells[5].get_text(strip=True)

    # Parse avg_temp if present
    avg_temp: float | None = None
    if len(cells) > 6:
        avg_temp_str = cells[6].get_text(strip=True)
        avg_temp = _parse_number(avg_temp_str)

    return {
        "read_date": _parse_date(read_date_str),
        "usage_kwh": _parse_number(usage_kwh_str),
        "num_days": int(_parse_number(num_days_str) or 0),
        "usage_per_day": _parse_number(usage_per_day_str),
        "cost_per_day": _parse_currency(cost_per_day_str),
        "total_charge": _parse_currency(total_charge_str),
        "avg_temp": avg_temp,
    }


def _parse_date(date_str: str) -> datetime.datetime:
    """Parse a date string into a datetime object.

    Tries common US date formats.

    Args:
        date_str: Date string like "01/15/2024" or "Jan 15, 2024".

    Returns:
        Parsed datetime object in UTC.

    Raises:
        ValueError: If the date string cannot be parsed.
    """
    formats = [
        "%m/%d/%Y",
        "%m/%d/%y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Could not parse date: {date_str!r}")


def _parse_number(value_str: str) -> float | None:
    """Parse a numeric string, stripping commas and whitespace.

    Args:
        value_str: String like "1,234.56" or "N/A".

    Returns:
        Parsed float, or None if the string is not numeric.
    """
    if not value_str:
        return None
    cleaned = value_str.replace(",", "").replace(" ", "").strip()
    if not cleaned or cleaned.lower() in ("n/a", "-", "--", ""):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_currency(value_str: str) -> float:
    """Parse a currency string, stripping '$' and commas.

    Args:
        value_str: String like "$123.45" or "$1,234.56".

    Returns:
        Parsed float value. Returns 0.0 if parsing fails.
    """
    if not value_str:
        return 0.0
    cleaned = value_str.replace("$", "").replace(",", "").replace(" ", "").strip()
    if not cleaned or cleaned.lower() in ("n/a", "-", "--"):
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        logger.warning("Could not parse currency value: %s", value_str)
        return 0.0


# ---------------------------------------------------------------------------
# Model conversion
# ---------------------------------------------------------------------------


def to_usage_points(scraped_data: list[dict]) -> list[model.UsagePoint]:
    """Convert scraped Eversource usage data to Home Assistant model objects.

    Creates a single UsagePoint containing a single MeterReading with
    IntervalBlocks derived from each row of scraped data.

    Args:
        scraped_data: List of dicts from parse_usage_table().

    Returns:
        List containing a single UsagePoint with the scraped data.
    """
    if not scraped_data:
        logger.warning("No scraped data to convert")
        return []

    interval_blocks: list[model.IntervalBlock] = []

    for idx, row in enumerate(scraped_data):
        read_date: datetime.datetime = row["read_date"]
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
        period_start = read_date - period_duration

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

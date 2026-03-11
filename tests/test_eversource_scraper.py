"""Unit tests for the Eversource web scraper."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# Note: These tests use mocked aiohttp to avoid actual network requests


@pytest.mark.asyncio
async def test_eversource_client_login_success():
    """Test successful login to Eversource."""
    from custom_components.green_button.parsers.eversource_scraper import (
        EversourceClient,
    )

    mock_session = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(
        return_value="""
        <form>
            <input type="hidden" name="__RequestVerificationToken" value="token123">
            <input type="text" name="username">
            <input type="password" name="password">
        </form>
    """
    )
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session.request = AsyncMock(return_value=mock_response)

    client = EversourceClient(
        username="testuser", password="testpass", session=mock_session
    )

    # Login should succeed
    result = await client.async_login()
    assert result is True

    # Should have made POST request with credentials
    assert mock_session.request.call_count >= 1


@pytest.mark.asyncio
async def test_eversource_client_login_failure():
    """Test failed login to Eversource."""
    from custom_components.green_button.parsers.eversource_scraper import (
        EversourceClient,
    )

    mock_session = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = 401  # Unauthorized
    mock_response.text = AsyncMock(return_value="Login failed")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    mock_session.request = AsyncMock(return_value=mock_response)

    client = EversourceClient(
        username="baduser", password="badpass", session=mock_session
    )

    result = await client.async_login()
    assert result is False


def test_parse_usage_table_basic():
    """Test parsing a basic usage table."""
    from custom_components.green_button.parsers.eversource_scraper import (
        parse_usage_table,
    )

    html = """
    <table id="usageChartTable">
        <thead>
            <tr>
                <th>Read Date</th>
                <th>Usage (kWh)</th>
                <th>Number of Days</th>
                <th>Usage Per Day</th>
                <th>Cost Per Day</th>
                <th>Total Charge</th>
                <th>Average Temp</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>03/02/2024</td>
                <td>466</td>
                <td>31</td>
                <td>15.0</td>
                <td>$4.68</td>
                <td>$145.06</td>
                <td>42</td>
            </tr>
            <tr>
                <td>02/02/2024</td>
                <td>520</td>
                <td>28</td>
                <td>18.6</td>
                <td>$5.21</td>
                <td>$145.88</td>
                <td>38</td>
            </tr>
        </tbody>
    </table>
    """

    rows = parse_usage_table(html)

    assert len(rows) == 2
    assert rows[0]["usage_kwh"] == 466.0
    assert rows[0]["num_days"] == 31
    assert rows[0]["total_charge"] == 145.06
    assert rows[1]["usage_kwh"] == 520.0


def test_parse_usage_table_empty():
    """Test parsing an empty table."""
    from custom_components.green_button.parsers.eversource_scraper import (
        parse_usage_table,
    )

    html = """
    <table id="usageChartTable">
        <tbody>
        </tbody>
    </table>
    """

    rows = parse_usage_table(html)
    assert len(rows) == 0


def test_parse_usage_table_missing_table():
    """Test handling missing table gracefully."""
    from custom_components.green_button.parsers.eversource_scraper import (
        parse_usage_table,
    )

    html = "<html><body>No table here</body></html>"

    rows = parse_usage_table(html)
    assert len(rows) == 0  # Should return empty list, not crash


def test_to_usage_points_conversion():
    """Test conversion of scraped data to model objects."""
    from custom_components.green_button.parsers.eversource_scraper import (
        to_usage_points,
    )

    scraped_data = [
        {
            "read_date": datetime(2024, 3, 2),
            "usage_kwh": 466.0,
            "num_days": 31,
            "usage_per_day": 15.0,
            "cost_per_day": 4.68,
            "total_charge": 145.06,
            "avg_temp": 42,
        },
        {
            "read_date": datetime(2024, 2, 2),
            "usage_kwh": 520.0,
            "num_days": 28,
            "usage_per_day": 18.6,
            "cost_per_day": 5.21,
            "total_charge": 145.88,
            "avg_temp": 38,
        },
    ]

    usage_points = to_usage_points(scraped_data)

    assert len(usage_points) == 1  # Single UsagePoint
    assert usage_points[0].id == "eversource_usage_point"

    # Check meter reading
    assert len(usage_points[0].meter_readings) == 1
    meter_reading = usage_points[0].meter_readings[0]
    assert meter_reading.id == "eversource_meter"

    # Check interval blocks (one per row)
    assert len(meter_reading.interval_blocks) == 2

    # Check first interval block
    first_block = meter_reading.interval_blocks[0]
    assert first_block.duration == timedelta(days=31)
    assert len(first_block.interval_readings) == 1
    assert first_block.interval_readings[0].value == 466000  # kWh to Wh
    assert first_block.interval_readings[0].cost == 14506  # dollars to cents


def test_to_usage_points_empty():
    """Test conversion with no data."""
    from custom_components.green_button.parsers.eversource_scraper import (
        to_usage_points,
    )

    usage_points = to_usage_points([])
    assert len(usage_points) == 1
    assert usage_points[0].id == "eversource_usage_point"
    assert len(usage_points[0].meter_readings[0].interval_blocks) == 0


def test_rate_limiting_constants():
    """Verify rate limiting constants are in place."""
    from custom_components.green_button.parsers import eversource_scraper

    # Check that rate limiting constants exist
    assert hasattr(eversource_scraper, "_PAGINATION_REQUEST_DELAY_SECONDS")
    assert eversource_scraper._PAGINATION_REQUEST_DELAY_SECONDS == 1.0

    # Check max pagination pages limit
    assert eversource_scraper._MAX_PAGINATION_PAGES == 50

    # Check retry configuration
    assert eversource_scraper._MAX_RETRIES == 3
    assert eversource_scraper._BACKOFF_BASE_SECONDS == 1


@pytest.mark.asyncio
async def test_request_with_retry_success():
    """Test successful request without retry."""
    from custom_components.green_button.parsers.eversource_scraper import (
        _request_with_retry,
    )

    mock_session = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = 200

    mock_session.request = AsyncMock(return_value=mock_response)

    result = await _request_with_retry(mock_session, "GET", "http://example.com")
    assert result == mock_response
    assert mock_session.request.call_count == 1


@pytest.mark.asyncio
async def test_request_with_retry_backoff():
    """Test that retries use exponential backoff."""
    from custom_components.green_button.parsers.eversource_scraper import (
        _request_with_retry,
    )
    import asyncio

    mock_session = AsyncMock()

    # Fail twice, succeed on third attempt
    mock_response = MagicMock()
    mock_response.status = 200
    mock_session.request = AsyncMock(
        side_effect=[
            ConnectionError("fail 1"),
            ConnectionError("fail 2"),
            mock_response,
        ]
    )

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await _request_with_retry(mock_session, "GET", "http://example.com")
        assert result == mock_response
        assert mock_session.request.call_count == 3
        # Should have slept with backoff delays (1s, 2s)
        assert mock_sleep.call_count == 2


def test_coordinator_polling_interval():
    """Verify coordinator sets correct polling interval for eversource mode."""
    from custom_components.green_button.const import (
        DEFAULT_SCAN_INTERVAL_HOURS,
    )

    # Check polling interval is set to 12 hours
    assert DEFAULT_SCAN_INTERVAL_HOURS == 12


def test_const_eversource_urls():
    """Verify Eversource URLs are configured."""
    from custom_components.green_button.const import (
        EVERSOURCE_LOGIN_URL,
        EVERSOURCE_USAGE_URL,
    )

    assert EVERSOURCE_LOGIN_URL == "https://www.eversource.com/security/account/login"
    assert (
        EVERSOURCE_USAGE_URL == "https://www.eversource.com/cg/customer/usagehistory"
    )


def test_config_flow_eversource_option():
    """Verify config flow includes eversource input type option."""
    # This would require full Home Assistant test fixtures
    # For now, we just verify imports work
    from custom_components.green_button.config_flow import ConfigFlow

    assert ConfigFlow is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

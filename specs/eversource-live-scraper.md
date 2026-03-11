# Plan: Eversource Live Usage Scraper

## Task Description
Redesign the Green Button Home Assistant integration to support live scraping of energy usage data from Eversource's website (https://www.eversource.com/cg/customer/usagehistory). The current integration ingests ESPI XML data from files or pasted content. The new focus is to add a scraper that authenticates against Eversource's login page, navigates to the usage history page, and extracts monthly kWh usage data and cost data from the HTML table rendered on the page.

## Objective
When this plan is complete, users will be able to configure the integration with their Eversource username and password, and the integration will periodically log in, scrape the usage history table, and create Home Assistant energy sensors with the scraped data — no manual XML file handling required.

## Problem Statement
The current integration requires users to manually obtain ESPI XML files and import them via config flow or service calls. Eversource does not provide easy ESPI XML exports for most residential customers. However, Eversource does display usage history on their authenticated web portal. Users need a way to automatically pull this data into Home Assistant without manual intervention.

## Solution Approach
1. **Add a new "eversource_scraper" input mode** to the config flow alongside the existing "file" and "xml" modes, allowing users to provide their Eversource username and password.
2. **Create a new scraper module** (`parsers/eversource_scraper.py`) that uses `aiohttp` with session-based authentication to log in to Eversource's portal and scrape the usage history HTML table.
3. **Parse the HTML table** within `<div class="tab-content usage-history">` → `<table id="usageChartTable">` to extract: Read Date, Usage (kWh), Number of Days, Usage Per Day, Cost Per Day, Total Charge, Average Temp.
4. **Convert scraped data to the existing `model.UsagePoint` / `model.MeterReading` / `model.IntervalBlock` / `model.IntervalReading` data structures** so the existing sensor, statistics, and coordinator infrastructure works unchanged.
5. **Add polling via `update_interval`** on the coordinator so data refreshes automatically (e.g., every 12-24 hours).
6. **Store credentials securely** using Home Assistant's config entry data (which is encrypted at rest).

### Authentication Strategy
The Eversource login page at `https://www.eversource.com/security/account/login` is a standard form-based login. The scraper will:
1. GET the login page to obtain any CSRF tokens / hidden form fields
2. POST credentials to the login endpoint
3. Follow redirects to the usage history page
4. Extract session cookies for subsequent requests

### Data Extraction Strategy
The usage history table (`#usageChartTable`) contains rows with:
- **Read Date** (e.g., `03/02/2026`) — maps to IntervalBlock start time
- **Usage (kWh)** (e.g., `466`) — maps to IntervalReading value
- **Number of Days** (e.g., `31`) — maps to IntervalBlock duration
- **Usage Per Day** — derived attribute
- **Cost Per Day** — derived attribute
- **Total Charge** (e.g., `$145.06`) — maps to IntervalReading cost
- **Average Temp** — extra state attribute

The page also has a "Show More" link that may load additional historical data via AJAX; the scraper should handle pagination to get all available data.

## Relevant Files
Use these files to complete the task:

- [config_flow.py](custom_components/green_button/config_flow.py) — Add new "eversource" input type with username/password fields
- [coordinator.py](custom_components/green_button/coordinator.py) — Add `update_interval` support for polling mode; integrate scraper data source
- [const.py](custom_components/green_button/const.py) — Add new constants for Eversource URLs, config keys
- [configs.py](custom_components/green_button/configs.py) — Update `ComponentConfig` to support scraper mode (no XML required)
- [model.py](custom_components/green_button/model.py) — No changes needed; scraped data will be converted to existing model classes
- [sensor.py](custom_components/green_button/sensor.py) — No changes needed; sensors already work with UsagePoint/MeterReading data
- [manifest.json](custom_components/green_button/manifest.json) — Add `aiohttp` and `beautifulsoup4` to requirements
- [strings.json](custom_components/green_button/strings.json) — Add UI strings for Eversource config step
- [translations/en.json](custom_components/green_button/translations/en.json) — Add English translations
- [__init__.py](custom_components/green_button/__init__.py) — No major changes needed
- [services.py](custom_components/green_button/services.py) — Optionally add a `refresh_eversource` service for manual refresh

### New Files
- [parsers/eversource_scraper.py](custom_components/green_button/parsers/eversource_scraper.py) — New module: Eversource login + HTML scraping + data conversion to model objects

## Implementation Phases

### Phase 1: Foundation
- Add new constants (`CONF_EVERSOURCE_USERNAME`, `CONF_EVERSOURCE_PASSWORD`, Eversource URLs)
- Update `manifest.json` to add `beautifulsoup4` dependency
- Update `strings.json` and `translations/en.json` with new config step strings

### Phase 2: Core Implementation
- Create `parsers/eversource_scraper.py` with:
  - `EversourceClient` class handling login session management
  - `async_login(username, password)` — authenticates and stores session cookies
  - `async_fetch_usage_history()` — fetches and parses the usage history page
  - `parse_usage_table(html)` — extracts data from `#usageChartTable` rows
  - `to_usage_points(scraped_data)` — converts scraped data to `model.UsagePoint` list
- Update `config_flow.py`:
  - Add "eversource" option to `input_type` selector
  - Add conditional username/password fields when "eversource" is selected
  - Validate credentials by attempting a test login during config flow
- Update `coordinator.py`:
  - Add `update_interval` (e.g., `timedelta(hours=12)`) when in scraper mode
  - In `_async_update_data()`, call scraper when config is eversource mode
- Update `configs.py`:
  - Allow `ComponentConfig.from_mapping()` to work without XML when in scraper mode

### Phase 3: Integration & Polish
- Handle "Show More" pagination on the usage history page
- Add error handling for:
  - Invalid credentials (show in config flow)
  - Session expiry (re-login automatically)
  - Website structure changes (graceful degradation with logging)
  - Network errors (retry with backoff via coordinator)
- Add a `refresh_eversource` service for on-demand data refresh
- Test the full flow end-to-end

## Team Orchestration

- You operate as the team lead and orchestrate the team to execute the plan.
- You're responsible for deploying the right team members with the right context to execute the plan.
- IMPORTANT: You NEVER operate directly on the codebase. You use `Task` and `Task*` tools to deploy team members to do the building, validating, testing, deploying, and other tasks.
  - This is critical. Your job is to act as a high level director of the team, not a builder.
  - Your role is to validate all work is going well and make sure the team is on track to complete the plan.
  - You'll orchestrate this by using the Task* Tools to manage coordination between the team members.
  - Communication is paramount. You'll use the Task* Tools to communicate with the team members and ensure they're on track to complete the plan.
- Take note of the session id of each team member. This is how you'll reference them.

### Team Members

- Builder
  - Name: builder-foundation
  - Role: Set up constants, manifest, strings, and translation files
  - Agent Type: builder
  - Resume: true

- Builder
  - Name: builder-scraper
  - Role: Implement the Eversource scraper module (login, fetch, parse, convert)
  - Agent Type: builder
  - Resume: true

- Builder
  - Name: builder-config-flow
  - Role: Update config flow, configs, and coordinator to support eversource scraper mode
  - Agent Type: builder
  - Resume: true

- Builder
  - Name: builder-polish
  - Role: Add pagination, error handling, refresh service, and final integration work
  - Agent Type: builder
  - Resume: true

- Builder
  - Name: validator-final
  - Role: Validate all acceptance criteria are met, run validation commands
  - Agent Type: validator
  - Resume: false

## Step by Step Tasks

- IMPORTANT: Execute every step in order, top to bottom. Each task maps directly to a `TaskCreate` call.
- Before you start, run `TaskCreate` to create the initial task list that all team members can see and execute.

### 1. Add Constants and Dependencies
- **Task ID**: add-constants-deps
- **Depends On**: none
- **Assigned To**: builder-foundation
- **Agent Type**: builder
- **Parallel**: true
- Add to `const.py`:
  - `CONF_INPUT_TYPE = "input_type"`
  - `CONF_EVERSOURCE_USERNAME = "eversource_username"`
  - `CONF_EVERSOURCE_PASSWORD = "eversource_password"`
  - `EVERSOURCE_LOGIN_URL = "https://www.eversource.com/security/account/login"`
  - `EVERSOURCE_USAGE_URL = "https://www.eversource.com/cg/customer/usagehistory"`
  - `DEFAULT_SCAN_INTERVAL_HOURS = 12`
- Add `beautifulsoup4` to `manifest.json` requirements list
- Update `strings.json` to add:
  - `eversource_username` and `eversource_password` data labels
  - "eversource" as an input_type option label
  - Error strings: `invalid_eversource_credentials`, `eversource_connection_error`
- Update `translations/en.json` to match

### 2. Create Eversource Scraper Module
- **Task ID**: create-scraper
- **Depends On**: add-constants-deps
- **Assigned To**: builder-scraper
- **Agent Type**: builder
- **Parallel**: false
- Create `custom_components/green_button/parsers/eversource_scraper.py`
- Implement `EversourceClient` class:
  - `__init__(self, username: str, password: str, session: aiohttp.ClientSession | None = None)`
  - `async def async_login(self) -> bool` — GET login page, extract CSRF/hidden fields, POST credentials, verify success by checking redirect or response content
  - `async def async_fetch_usage_history(self) -> str` — GET usage history page HTML after login
  - `async def async_get_full_usage_history(self) -> str` — Handle "Show More" pagination by detecting and calling the AJAX endpoint
  - `async def async_close(self)` — Clean up session
- Implement `parse_usage_table(html: str) -> list[dict]`:
  - Use BeautifulSoup to find `table#usageChartTable`
  - Extract each `<tr>` in `<tbody>`: read_date, usage_kwh, num_days, usage_per_day, cost_per_day, total_charge, avg_temp
  - Return list of dicts with parsed values (dates as datetime, numbers as float/int, costs stripped of `$`)
- Implement `to_usage_points(scraped_data: list[dict]) -> list[model.UsagePoint]`:
  - Create a single `UsagePoint` with `id="eversource_usage_point"`, `sensor_device_class=ENERGY`
  - Create one `MeterReading` with `id="eversource_meter"`
  - For each scraped row, create an `IntervalBlock` with:
    - `start` = read_date minus num_days (the billing period start)
    - `duration` = timedelta(days=num_days)
    - One `IntervalReading` per block with:
      - `value` = usage_kwh (as Wh, so multiply by 1000)
      - `cost` = total_charge in cents (multiply by 100)
      - `start` / `duration` matching the block
  - Create a `ReadingType` with: `power_of_ten_multiplier=0`, `unit_of_measurement="Wh"`, `currency="USD"`, `interval_length=86400*num_days`
- Add proper logging throughout
- Handle common error cases (login failure, unexpected HTML structure, missing table)

### 3. Update Config Flow for Eversource Mode
- **Task ID**: update-config-flow
- **Depends On**: create-scraper
- **Assigned To**: builder-config-flow
- **Agent Type**: builder
- **Parallel**: false
- In `config_flow.py`:
  - Add "eversource" to the `input_type` selector options (alongside "file" and "xml")
  - When `input_type == "eversource"`, show `eversource_username` and `eversource_password` fields
  - On submit with eversource mode:
    - Import and instantiate `EversourceClient`
    - Call `async_login()` to validate credentials
    - If login fails, return error `invalid_eversource_credentials`
    - If login succeeds, call `async_fetch_usage_history()` and `parse_usage_table()` + `to_usage_points()` to validate data is retrievable
    - Store username and password in config entry data
    - Set `unique_id` to `eversource_{username}` to prevent duplicate entries
  - Hide XML-related fields when eversource is selected (or just ignore them)
- In `configs.py`:
  - Update `ComponentConfig.from_mapping()` to handle case where no XML is provided but `input_type == "eversource"`
  - When in eversource mode, create a placeholder `ComponentConfig` with empty meter_reading_configs (they'll be populated by the coordinator on first fetch)

### 4. Update Coordinator for Polling Mode
- **Task ID**: update-coordinator
- **Depends On**: update-config-flow
- **Assigned To**: builder-config-flow
- **Agent Type**: builder
- **Parallel**: false
- In `coordinator.py`:
  - Import `datetime.timedelta` and the eversource scraper
  - In `__init__`, check if config entry's `input_type` is `"eversource"`:
    - If so, set `update_interval=timedelta(hours=12)` (or from const)
    - Store username/password from config entry data
  - In `_async_update_data()`:
    - If eversource mode, instantiate `EversourceClient`, login, fetch, parse, convert to usage points
    - Update `self.usage_points` with the scraped data
    - Return `{"usage_points": usage_points}`
    - Handle errors (login failure, network, parsing) by raising `UpdateFailed`
  - Ensure `async_load_stored_data()` gracefully handles eversource mode (no stored XML)

### 5. Add Error Handling, Pagination, and Refresh Service
- **Task ID**: add-polish
- **Depends On**: update-coordinator
- **Assigned To**: builder-polish
- **Agent Type**: builder
- **Parallel**: false
- In the scraper module:
  - Implement "Show More" handling — inspect the page for `#show_more` link and determine if it triggers an AJAX call; implement pagination if so
  - Add retry logic for transient network errors
  - Add session reuse / cookie persistence to avoid re-logging in on every poll
- In `services.py`:
  - Add a `refresh_eversource` service that forces an immediate coordinator refresh for eversource-mode entries
- Test that the coordinator properly re-authenticates if the session expires between polls

### 6. Final Validation
- **Task ID**: validate-all
- **Depends On**: add-constants-deps, create-scraper, update-config-flow, update-coordinator, add-polish
- **Assigned To**: validator-final
- **Agent Type**: validator
- **Parallel**: false
- Run all validation commands
- Verify acceptance criteria met
- Check that existing XML/file flow still works unchanged
- Verify no import errors or circular dependencies

## Acceptance Criteria
- Users can select "Eversource" as an input type in the config flow and provide username + password
- The integration successfully authenticates against Eversource's login page
- The integration scrapes the usage history table and creates energy sensors with kWh and cost data
- Data refreshes automatically every 12 hours (configurable)
- Existing file/xml input modes continue to work unchanged
- Invalid credentials produce a clear error in the config flow
- Session expiry is handled gracefully with automatic re-authentication
- The `#usageChartTable` data (Read Date, Usage kWh, Number of Days, Total Charge, Average Temp) is fully extracted
- Sensors appear in the Home Assistant Energy Dashboard

## Validation Commands
Execute these commands to validate the task is complete:

- `python -m py_compile custom_components/green_button/parsers/eversource_scraper.py` — Verify scraper module compiles
- `python -m py_compile custom_components/green_button/config_flow.py` — Verify config flow compiles
- `python -m py_compile custom_components/green_button/coordinator.py` — Verify coordinator compiles
- `python -m py_compile custom_components/green_button/configs.py` — Verify configs compile
- `python -m py_compile custom_components/green_button/const.py` — Verify constants compile
- `python -m py_compile custom_components/green_button/services.py` — Verify services compile
- `python -c "from custom_components.green_button.parsers import eversource_scraper; print('Import OK')"` — Verify scraper is importable
- `python -c "import json; json.load(open('custom_components/green_button/manifest.json')); print('manifest OK')"` — Verify manifest is valid JSON
- `python -c "import json; json.load(open('custom_components/green_button/strings.json')); print('strings OK')"` — Verify strings is valid JSON

## Notes
- **Security**: Eversource credentials are stored in the HA config entry data, which is encrypted at rest by Home Assistant. The password should be stored but never logged.
- **Dependencies**: `beautifulsoup4` needs to be added to `manifest.json` requirements. `aiohttp` is already available in the Home Assistant runtime (part of HA core).
- **Website Changes**: Eversource may change their website structure at any time. The scraper should log warnings when expected HTML elements are missing and degrade gracefully rather than crashing.
- **Rate Limiting**: The default 12-hour polling interval is conservative to avoid triggering any rate limiting or account lockout on Eversource's side.
- **"Show More" Button**: The usage history page initially shows ~5 rows. The `#show_more` anchor likely triggers a JavaScript AJAX call to load more data. The scraper needs to reverse-engineer this endpoint or simulate the request to get full history.
- **CSRF Tokens**: Many login forms use CSRF tokens. The scraper must extract any `__RequestVerificationToken` or similar hidden fields from the login form and include them in the POST request.
- **Two-Factor Auth**: If Eversource implements 2FA, the scraper will need additional handling. This is out of scope for the initial implementation but should be noted.
- **Install new deps**: Use `pip install beautifulsoup4` or add to HACS requirements. For development, use `pip install beautifulsoup4`.

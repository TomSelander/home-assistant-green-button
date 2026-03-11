"""Constants for the Green Button integration."""
from typing import Final

DOMAIN: Final = "green_button"
# INTEGRATION_SERVICE_DATA_KEY = "integration_service"

# Input type configuration
CONF_INPUT_TYPE: Final = "input_type"

# Eversource configuration
CONF_EVERSOURCE_USERNAME: Final = "eversource_username"
CONF_EVERSOURCE_PASSWORD: Final = "eversource_password"
EVERSOURCE_LOGIN_URL: Final = "https://www.eversource.com/security/account/login"
EVERSOURCE_USAGE_URL: Final = "https://www.eversource.com/cg/customer/usagehistory"
DEFAULT_SCAN_INTERVAL_HOURS: Final = 12

# Service names
SERVICE_REFRESH_EVERSOURCE: Final = "refresh_eversource"


# class _CustomEntitiesParams:
#     NAME: Final = "name"
#     USAGE_POINT_HREF: Final = "usage_point_href"
#     ENERGY_UNIT: Final = "energy_unit"
#     COST_CURRENCY: Final = "cost_currency"


# @final
# class ConfigParams(_CustomEntitiesParams):
#     @classmethod
#     def make_schema(cls, hass: HomeAssistant) -> vol.Schema:
#         currency = hass.config.currency
#         return vol.Schema(
#             {
#                 vol.Required(cls.NAME): str,
#                 vol.Required(cls.USAGE_POINT_HREF): str,
#                 vol.Required(
#                     cls.ENERGY_UNIT, default=UnitOfEnergy.KILO_WATT_HOUR
#                 ): vol.In([unit.value for unit in UnitOfEnergy]),
#                 vol.Required(cls.COST_CURRENCY, default=currency): cv.currency,
#             }
#         )


# @final
# class OptionsParams(_CustomEntitiesParams):
#     @classmethod
#     def make_schema(cls) -> vol.Schema:
#         return vol.Schema(
#             {
#                 vol.Required(
#                     cls.USAGE_POINT_HREF,
#                 ): str,
#                 vol.Required(cls.ENERGY_UNIT): vol.In(
#                     [unit.value for unit in UnitOfEnergy]
#                 ),
#                 vol.Required(cls.COST_CURRENCY): cv.currency,
#             }
#         )

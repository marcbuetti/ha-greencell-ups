"""Constants for the Green Cell UPS integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "greencell_ups"

CONF_ENABLE_CONTROLS: Final = "enable_controls"

DEFAULT_PORT: Final = 8080
DEFAULT_SCAN_INTERVAL: Final = 10
MIN_SCAN_INTERVAL: Final = 3

# Specification / vendor data hardly ever changes - refresh it this often (seconds).
INFO_REFRESH: Final = 3600

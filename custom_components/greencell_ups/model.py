"""Interpretation of the GC UPS App payload. No Home Assistant imports (unit-testable)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# UPS status as shown by the integration (sensor "status", device class enum)
STATUS_ONLINE = "online"
STATUS_ON_BATTERY = "on_battery"
STATUS_BATTERY_LOW = "battery_low"
STATUS_TEST = "test"
STATUS_FAULT = "fault"
STATUS_SHUTDOWN = "shutdown"
STATUS_DISCONNECTED = "disconnected"
STATUSES = [
    STATUS_ONLINE,
    STATUS_ON_BATTERY,
    STATUS_BATTERY_LOW,
    STATUS_TEST,
    STATUS_FAULT,
    STATUS_SHUTDOWN,
    STATUS_DISCONNECTED,
]


def pick(raw: dict[str, Any], *keys: str) -> Any:
    """First present key - accepts camelCase (HTTP) and snake_case (UI route names)."""
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return None


def measurement(raw: dict[str, Any], *keys: str) -> float | None:
    """Number or None. Negative values are the app's "don't know" (-1 without probe/USB).

    0 stays valid: 0 V at the input really means "no mains".
    """
    value = pick(raw, *keys)
    if isinstance(value, bool):
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    return None if num < 0 else num


def flag(raw: dict[str, Any], *keys: str) -> bool | None:
    value = pick(raw, *keys)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str) and value.lower() in ("true", "false", "1", "0"):
        return value.lower() in ("true", "1")
    return None


@dataclass
class UPSData:
    """One poll: current parameters plus the (rarely changing) device information."""

    current: dict[str, Any]
    nominal: dict[str, Any] = field(default_factory=dict)
    spec: dict[str, Any] = field(default_factory=dict)
    info: dict[str, Any] = field(default_factory=dict)

    # --- link -------------------------------------------------------------------------
    @property
    def connected(self) -> bool:
        """The app sees the UPS on USB. Without it every value is a placeholder."""
        return flag(self.current, "connected", "is_connected") is True

    def _live(self, *keys: str) -> float | None:
        return measurement(self.current, *keys) if self.connected else None

    def _live_flag(self, *keys: str) -> bool | None:
        return flag(self.current, *keys) if self.connected else None

    # --- measurements -----------------------------------------------------------------
    @property
    def battery_level(self) -> float | None:
        return self._live("batteryLevel", "battery_level")

    @property
    def battery_voltage(self) -> float | None:
        return self._live("batteryVoltage", "battery_voltage")

    @property
    def input_voltage(self) -> float | None:
        return self._live("inputVoltage", "input_voltage")

    @property
    def input_voltage_fault(self) -> float | None:
        return self._live("inputVoltageFault", "input_voltage_fault")

    @property
    def output_voltage(self) -> float | None:
        return self._live("outputVoltage", "output_voltage")

    @property
    def input_frequency(self) -> float | None:
        return self._live("inputFrequency", "input_frequency")

    @property
    def load(self) -> float | None:
        return self._live("load")

    @property
    def temperature(self) -> float | None:
        return self._live("temperature")

    @property
    def rated_power(self) -> float | None:
        """Rated real power in W from the device specification (e.g. 900)."""
        return measurement(self.spec, "power")

    @property
    def output_power(self) -> float | None:
        """Estimated output power: load % x rated W. The UPS itself does not measure watts."""
        if self.load is None or not self.rated_power:
            return None
        return round(self.load / 100 * self.rated_power, 1)

    # --- flags ------------------------------------------------------------------------
    @property
    def utility_fail(self) -> bool | None:
        """Mains gone, the load runs on battery."""
        return self._live_flag("utilityFail", "is_utility_fail")

    @property
    def battery_low(self) -> bool | None:
        return self._live_flag("batteryLow", "is_battery_low")

    @property
    def failed(self) -> bool | None:
        return self._live_flag("failed", "is_failed")

    @property
    def shutdown_active(self) -> bool | None:
        return self._live_flag("shutdownActive", "is_shutdown_active")

    @property
    def test_in_progress(self) -> bool | None:
        return self._live_flag("testInProgress", "is_test_in_progress")

    @property
    def beeper_on(self) -> bool | None:
        return self._live_flag("beeperOn", "is_beeper_on")

    @property
    def bypass_boost(self) -> bool | None:
        """AVR boost/buck active (the UPS corrects the mains voltage)."""
        return self._live_flag("bypassBoost", "is_bypass_boost")

    @property
    def charging(self) -> bool | None:
        """Mains present and battery above its float threshold.

        The vendor UI's "charging" is a fixed label; this is derived: a 12 V lead-acid block
        sits at 13.5-13.8 V while charging, above batteryVoltageHighNominal, and drops below
        it when discharging. Scaled by the number of blocks where the app reports the high
        nominal per block.
        """
        if not self.connected or self.utility_fail is not False:
            return None
        volt = self.battery_voltage
        high = measurement(
            self.nominal, "batteryVoltageHighNominal", "battery_voltage_high_nominal"
        )
        if volt is None or not high:
            return None
        return volt > high

    @property
    def status(self) -> str:
        """Single summary state, most severe first.

        Note: "offline" in the payload describes the topology (standby/line-interactive
        instead of double conversion) and is True in normal operation - never a fault.
        """
        if not self.connected:
            return STATUS_DISCONNECTED
        if self.failed:
            return STATUS_FAULT
        if self.shutdown_active:
            return STATUS_SHUTDOWN
        if self.battery_low:
            return STATUS_BATTERY_LOW
        if self.utility_fail:
            return STATUS_ON_BATTERY
        if self.test_in_progress:
            return STATUS_TEST
        return STATUS_ONLINE

    # --- device info ------------------------------------------------------------------
    @property
    def model(self) -> str | None:
        name = pick(self.spec, "name", "description")
        return None if name in (None, "", "unknown") else str(name)

    @property
    def model_id(self) -> str | None:
        ident = pick(self.spec, "id")
        return None if ident in (None, "", "unknown") else str(ident)

    @property
    def manufacturer(self) -> str:
        for key in ("manufacturer", "vendor"):
            value = str(self.info.get(key) or "").strip()
            if value and value.lower() not in ("unknown", "undefined", "-1"):
                return value
        return "Green Cell"

    @property
    def firmware(self) -> str | None:
        value = str(self.info.get("info") or "").strip()
        return value if value and value.lower() not in ("unknown", "undefined", "-1") else None

"""Binary sensory: „Trzeba nakarmić” i stan połączenia z Firebase."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import KarmienieConfigEntry
from .entity import KarmienieEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KarmienieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [FeedingDueSensor(coordinator, "feeding_due"), ConnectionSensor(coordinator, "connection")]
    )


class FeedingDueSensor(KarmienieEntity, BinarySensorEntity):
    """Włączony, gdy od ostatniego karmienia minął próg (domyślnie 3 h, jak w aplikacji)."""

    _attr_icon = "mdi:baby-bottle-outline"

    @property
    def is_on(self) -> bool | None:
        last = self.snapshot.last_feeding
        if last is None:
            return None
        return dt_util.utcnow() - last.time >= self.coordinator.threshold

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        last = self.snapshot.last_feeding
        threshold = self.coordinator.threshold
        return {
            "ostatnie_karmienie": last.time.isoformat() if last else None,
            "opis": last.describe() if last else None,
            "autor": last.author if last else None,
            "termin": (last.time + threshold).isoformat() if last else None,
            "prog_h": threshold.total_seconds() / 3600,
        }


class ConnectionSensor(KarmienieEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.connected

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "ostatni_blad": self.coordinator.last_error,
            "wpisow_w_oknie": len(self.snapshot.entries),
        }

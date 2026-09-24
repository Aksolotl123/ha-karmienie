"""Sensory: ostatnie/następne karmienie, liczniki dnia, leki, waga."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfMass, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import KarmienieConfigEntry
from .coordinator import KarmienieCoordinator
from .entity import KarmienieEntity
from .model import Entry, Snapshot


@dataclass(frozen=True, kw_only=True)
class KarmienieSensorDescription(SensorEntityDescription):
    value_fn: Callable[[Snapshot, KarmienieCoordinator], datetime | int | float | None]
    entry_fn: Callable[[Snapshot], Entry | None] | None = None


def _last_time(entry: Entry | None) -> datetime | None:
    return entry.time if entry else None


def _next_feeding(s: Snapshot, c: KarmienieCoordinator) -> datetime | None:
    last = s.last_feeding
    return last.time + c.threshold if last else None


def _minutes_since(s: Snapshot, _c: KarmienieCoordinator) -> int | None:
    last = s.last_feeding
    if last is None:
        return None
    return int((dt_util.utcnow() - last.time).total_seconds() // 60)


def _weight(s: Snapshot, _c: KarmienieCoordinator) -> float | None:
    last = s.last_weight
    return float(last.details["weight"]) if last else None


SENSORS: tuple[KarmienieSensorDescription, ...] = (
    KarmienieSensorDescription(
        key="last_feeding",
        icon="mdi:baby-bottle",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s, _c: _last_time(s.last_feeding),
        entry_fn=lambda s: s.last_feeding,
    ),
    KarmienieSensorDescription(
        key="next_feeding",
        icon="mdi:clock-alert-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_feeding,
    ),
    KarmienieSensorDescription(
        key="minutes_since_feeding",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_minutes_since,
    ),
    KarmienieSensorDescription(
        key="milk_today",
        icon="mdi:cup-water",
        native_unit_of_measurement="ml",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda s, _c: s.milk_on(dt_util.now().date()),
    ),
    KarmienieSensorDescription(
        key="feedings_today",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s, _c: len(s.feedings_on(dt_util.now().date())),
    ),
    KarmienieSensorDescription(
        key="last_ibuprofen",
        icon="mdi:pill",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s, _c: _last_time(s.last_nlpz("Ibuprofen")),
        entry_fn=lambda s: s.last_nlpz("Ibuprofen"),
    ),
    KarmienieSensorDescription(
        key="last_paracetamol",
        icon="mdi:pill",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda s, _c: _last_time(s.last_nlpz("Paracetamol")),
        entry_fn=lambda s: s.last_nlpz("Paracetamol"),
    ),
    KarmienieSensorDescription(
        key="weight",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=_weight,
        entry_fn=lambda s: s.last_weight,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KarmienieConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(KarmienieSensor(coordinator, d) for d in SENSORS)


class KarmienieSensor(KarmienieEntity, SensorEntity):
    entity_description: KarmienieSensorDescription

    def __init__(
        self, coordinator: KarmienieCoordinator, description: KarmienieSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> datetime | int | float | None:
        return self.entity_description.value_fn(self.snapshot, self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.entry_fn is None:
            return None
        entry = self.entity_description.entry_fn(self.snapshot)
        if entry is None:
            return None
        return {"opis": entry.describe(), "autor": entry.author}

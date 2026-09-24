"""Wspólna baza encji."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KarmienieCoordinator
from .model import Snapshot


class KarmienieEntity(CoordinatorEntity[KarmienieCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: KarmienieCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Karmienie",
            manufacturer="Karmienie Dziecka",
            model="Firebase Realtime Database",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def snapshot(self) -> Snapshot:
        return self.coordinator.data or Snapshot()

    @property
    def available(self) -> bool:
        return self.coordinator.data_available

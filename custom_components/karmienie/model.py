"""Model wpisów z /feedings i obliczenia jak w aplikacji Android."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .const import FEEDING_TYPES, NLPZ_DRUGS, TYPE_NLPZ, TYPE_WEIGHT


@dataclass(frozen=True, slots=True)
class Entry:
    key: str
    time: datetime
    type: str
    details: dict[str, Any]
    author: str | None

    @property
    def is_feeding(self) -> bool:
        return self.type in FEEDING_TYPES

    @property
    def milk_ml(self) -> int:
        """Ilość mleka: Jedzenie/Mleko albo stary typ Butelka."""
        if self.type == "Butelka" or (
            self.type == "Jedzenie" and self.details.get("subType") == "Mleko"
        ):
            amount = self.details.get("amount")
            if isinstance(amount, (int, float)):
                return int(amount)
        return 0

    def describe(self) -> str:
        """Opis jak feedingDescription() w Cloud Function."""
        d = self.details
        if self.type == "Jedzenie":
            if d.get("subType") == "Mleko":
                return f"Mleko {d.get('amount') or 0} ml"
            if d.get("subType") == "Pokarm stały":
                return f"Pokarm stały: {d.get('mealName') or ''}".strip()
            return "Jedzenie"
        if self.type == "Butelka":
            return f"Mleko {d.get('amount') or 0} ml"
        if self.type == TYPE_NLPZ:
            label = d.get("nlpzDrug") or "NLPZ"
            amount = d.get("nlpzAmount")
            if isinstance(amount, (int, float)):
                if d.get("nlpzUnit") == "mg":
                    return f"{label} {round(amount)} mg"
                return f"{label} {amount:.1f} ml"
            return label
        if self.type == TYPE_WEIGHT:
            return f"Waga: {float(d.get('weight') or 0):.3f} kg"
        return self.type or "Nieznane"


def parse_entry(key: str, raw: Any) -> Entry | None:
    if not isinstance(raw, dict):
        return None
    start = raw.get("startTime")
    if not isinstance(start, (int, float)) or start <= 0:
        return None
    details = raw.get("details")
    return Entry(
        key=key,
        time=dt_util.utc_from_timestamp(start / 1000),
        type=str(raw.get("type") or ""),
        details=details if isinstance(details, dict) else {},
        author=raw.get("authorName"),
    )


@dataclass(slots=True)
class Snapshot:
    """Stan wyliczony z okna ostatnich wpisów (posortowany po czasie rosnąco)."""

    entries: list[Entry] = field(default_factory=list)

    @classmethod
    def from_raw(cls, feedings: dict[str, Any]) -> Snapshot:
        parsed = (parse_entry(k, v) for k, v in feedings.items())
        return cls(sorted((e for e in parsed if e), key=lambda e: e.time))

    def _last(self, pred) -> Entry | None:
        now = dt_util.utcnow()
        # Wpisy z przyszłości (błędna data w formularzu) nie mogą przesunąć terminu.
        for entry in reversed(self.entries):
            if entry.time <= now and pred(entry):
                return entry
        return None

    @property
    def last_feeding(self) -> Entry | None:
        return self._last(lambda e: e.is_feeding)

    def last_nlpz(self, drug: str) -> Entry | None:
        return self._last(
            lambda e: e.type == TYPE_NLPZ and e.details.get("nlpzDrug") == drug
        )

    @property
    def last_weight(self) -> Entry | None:
        return self._last(
            lambda e: e.type == TYPE_WEIGHT
            and isinstance(e.details.get("weight"), (int, float))
        )

    def feedings_on(self, day: date) -> list[Entry]:
        return [
            e for e in self.entries if e.is_feeding and dt_util.as_local(e.time).date() == day
        ]

    def milk_on(self, day: date) -> int:
        return sum(e.milk_ml for e in self.feedings_on(day))


__all__ = ["Entry", "NLPZ_DRUGS", "Snapshot", "parse_entry"]

"""Stałe integracji Karmienie Dziecka."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "karmienie"

CONF_API_KEY = "api_key"
CONF_DATABASE_URL = "database_url"
CONF_THRESHOLD_HOURS = "threshold_hours"

# Jak FeedingReminderScheduler.THRESHOLD_MS w aplikacji.
DEFAULT_THRESHOLD_HOURS = 3.0

# Jak FeedingReminderReceiver.LIMIT — orderBy="$key" nie wymaga .indexOn,
# a klucze push są chronologiczne.
FEEDINGS_LIMIT = 200

# Typy wpisów liczone jako karmienie (jak filtr w FeedingReminderScheduler).
FEEDING_TYPES = ("Jedzenie", "Butelka")
TYPE_NLPZ = "NLPZ"
TYPE_WEIGHT = "Waga"
NLPZ_DRUGS = ("Ibuprofen", "Paracetamol")

# Krótkie zerwanie strumienia nie powinno od razu robić encji „unavailable”
# (automatyzacja światła reaguje na przejścia stanów binary_sensora).
UNAVAILABLE_AFTER = timedelta(minutes=10)

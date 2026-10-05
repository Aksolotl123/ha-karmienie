"""Stałe integracji Karmienie Dziecka."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import urlsplit

DOMAIN = "karmienie"

CONF_API_KEY = "api_key"
CONF_DATABASE_URL = "database_url"
CONF_THRESHOLD_HOURS = "threshold_hours"

# Token ID trafia jako parametr ?auth= pod adres bazy — dopuszczamy tylko domeny
# Firebase RTDB, żeby nie wysłać go pod dowolny wpisany adres.
DATABASE_URL_SUFFIXES = (".firebaseio.com", ".firebasedatabase.app")


def is_valid_database_url(url: str) -> bool:
    """Czy adres wygląda na bazę Firebase RTDB (https, domena Firebase, bez ścieżki)."""
    try:
        parts = urlsplit(str(url).strip())
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return False
    return (
        parts.scheme == "https"
        and host.endswith(DATABASE_URL_SUFFIXES)
        and port in (None, 443)
        and parts.username is None
        and parts.password is None
        and parts.path in ("", "/")
        and not parts.query
        and not parts.fragment
    )

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

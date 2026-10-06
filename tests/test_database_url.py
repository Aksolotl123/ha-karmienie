"""Testy walidacji adresu bazy (const.is_valid_database_url).

Moduł ładujemy po ścieżce pliku, żeby nie importować pakietu integracji
(jego __init__ wymaga Home Assistanta). Adresy w testach są zmyślone.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

_CONST = Path(__file__).parents[1] / "custom_components" / "karmienie" / "const.py"
_spec = spec_from_file_location("karmienie_const", _CONST)
const = module_from_spec(_spec)
_spec.loader.exec_module(const)


@pytest.mark.parametrize(
    "url",
    [
        "https://przyklad-default-rtdb.europe-west1.firebasedatabase.app",
        "https://przyklad-default-rtdb.europe-west1.firebasedatabase.app/",
        "https://przyklad-default-rtdb.firebaseio.com",
        "https://PRZYKLAD.FirebaseIO.com/",
        "  https://przyklad.firebaseio.com  ",
        "https://przyklad.firebaseio.com:443",
    ],
)
def test_poprawne_adresy(url):
    assert const.is_valid_database_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "przyklad.firebaseio.com",
        "http://przyklad.firebaseio.com",
        "ftp://przyklad.firebaseio.com",
        "https://firebaseio.com",
        "https://przyklad.firebaseio.com.zly.example",
        "https://przyklad-firebaseio.com",
        "https://zly.example/przyklad.firebaseio.com",
        "https://zly.example?x=.firebaseio.com",
        "https://user:pass@przyklad.firebaseio.com",
        "https://przyklad.firebaseio.com@zly.example",
        "https://przyklad.firebaseio.com:8443",
        "https://przyklad.firebaseio.com/feedings",
        "https://przyklad.firebaseio.com/?auth=x",
        "https://przyklad.firebaseio.com/#x",
        "https://przyklad.firebaseio.com:abc",
        # backslash zostaje w hoście po urlsplit
        "https://zly.example\\przyklad.firebaseio.com",
        "https://zly.example\\.firebaseio.com",
        # znaki pełnej szerokości i inne spoza ASCII
        "https://ｐｒｚｙｋｌａｄ.firebaseio.com",
        "https://przyklad．firebaseio．com",
        "https://przykład.firebaseio.com",
        # puste etykiety
        "https://.firebaseio.com",
        "https://przyklad..firebaseio.com",
        # biały znak w hoście
        "https://prz yklad.firebaseio.com",
        # pusty query/fragment na końcu
        "https://przyklad.firebaseio.com/?",
        "https://przyklad.firebaseio.com/#",
        "https://przyklad.firebaseio.com?",
    ],
)
def test_odrzucone_adresy(url):
    assert not const.is_valid_database_url(url)

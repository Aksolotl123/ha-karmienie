# Karmienie Dziecka — integracja Home Assistant

Czyta na żywo wpisy z aplikacji **Karmienie Dziecka** (Firebase Realtime Database, węzeł
`feedings/`) i wystawia je w Home Assistant, np. żeby zapalić światło na czerwono, gdy od
ostatniego karmienia minęły 3 godziny.

## Encje

| Encja | Opis |
|---|---|
| `binary_sensor.karmienie_trzeba_nakarmic` | `on`, gdy od ostatniego wpisu **Jedzenie/Butelka** minął próg (domyślnie 3 h — jak przypomnienie w aplikacji) |
| `sensor.karmienie_ostatnie_karmienie` | czas ostatniego karmienia (+ opis, autor) |
| `sensor.karmienie_nastepne_karmienie` | ostatnie karmienie + próg |
| `sensor.karmienie_od_ostatniego_karmienia` | minuty od ostatniego karmienia |
| `sensor.karmienie_mleko_dzis` / `sensor.karmienie_karmienia_dzis` | suma ml mleka i liczba karmień w bieżącej dobie |
| `sensor.karmienie_ostatni_ibuprofen` / `..._paracetamol` | ostatnie podanie leku |
| `sensor.karmienie_waga` | ostatni pomiar wagi |
| `binary_sensor.karmienie_polaczenie_z_firebase` | diagnostyka strumienia |

Próg zmienisz w **Ustawienia → Urządzenia i usługi → Karmienie Dziecka → Konfiguruj**.

## Jak to działa

* Logowanie osobnym kontem Firebase (e-mail/hasło) — bez klucza admina w HA.
* Strumień REST (Server-Sent Events) na `feedings.json?orderBy="$key"&limitToLast=200` —
  zmiany docierają w ~1 s; token odnawiany co godzinę.
* Krótka przerwa w połączeniu (< 10 min) nie robi encji `unavailable`.

## Konto dla Home Assistant

Jednorazowo (z katalogu repo, potrzebny klucz service account projektu):

```
GOOGLE_APPLICATION_CREDENTIALS=<plik klucza> FIREBASE_DATABASE_URL=<adres bazy> node scripts/create_ha_user.js
```

Skrypt włącza logowanie e-mail/hasło, zakłada konto `home-assistant@karmienie.local`
i ustawia `users/{uid}` = `allowed: true`, `appVersion: 99999`. Wypisze hasło do wpisania w HA.

## Instalacja

HACS → ⋮ → Niestandardowe repozytoria → adres tego repo, kategoria *Integracja* →
pobierz → restart HA → **Dodaj integrację → Karmienie Dziecka**.

W formularzu podajesz e-mail i hasło konta HA oraz **adres Realtime Database** i **klucz
Web API** swojego projektu Firebase (Konsola Firebase → Ustawienia projektu). Repozytorium
celowo nie zawiera żadnych kluczy ani adresów projektu.

# Instrukcje dla agentów AI

## Zasady projektu

- Dokumentacja aplikacji i dziennik prac są prowadzone po polsku.
- Nazwy zmiennych, funkcji, procedur, klas i pozostałych identyfikatorów w kodzie są po angielsku.
- Przed rozpoczęciem pracy przeczytaj `README.md` i `docs/INTERACTIONS.md` oraz instrukcje właściwe dla edytowanych katalogów.
- Zapisuj każdą interakcję z użytkownikiem w `docs/INTERACTIONS.md`: treść polecenia, podjęte decyzje, wykonane zmiany, weryfikację i otwarte kwestie. Nie zapisuj sekretów ani prywatnego toku rozumowania.
- Przed zakończeniem każdej iteracji zaktualizuj dziennik, aby inny agent mógł kontynuować pracę.
- Po dodaniu projektu do Git każda iteracja wprowadzająca zmiany musi zakończyć się commitem obejmującym także aktualizację dokumentacji i dziennika. Nie inicjalizuj repozytorium bez polecenia użytkownika. Nie dodawaj do commita niezwiązanych zmian użytkownika ani sekretów.
- Jeśli commit lub weryfikacja są zablokowane, zapisz przyczynę i jasno poinformuj użytkownika. Nie deklaruj wykonania operacji bez potwierdzenia.

## CodeGraph

Jeśli w katalogu głównym istnieje `.codegraph/`, używaj CodeGraph przed wyszukiwaniem tekstowym i czytaniem plików w celu poznania lub zlokalizowania kodu. Preferuj narzędzie MCP `codegraph_explore` albo polecenie `codegraph explore "<symbole lub pytanie>"`. Jeśli `.codegraph/` nie istnieje, pomiń CodeGraph; decyzję o indeksowaniu podejmuje użytkownik.

# Pomiar wyszukiwania — 2026-10-28

Badano trzy tytuły: Inception (2010), Interstellar (2014), The Matrix (1999). Obie próby wykonywały rzeczywiste zapytania Filmweb i IMDb oraz przygotowały osobny, początkowo pusty indeks ocen IMDb. Nie używano klucza TMDB, więc porównanie nie mierzy jego opóźnień.

| Pomiar | Wynik |
|---|---:|
| Dotychczasowa seria sekwencyjna | 53,205 s |
| Suma czasu Filmweb w tej serii, wraz z ograniczeniem żądań | 41,929 s |
| Suma czasu odpowiedzi/oczekiwania IMDb, bez zbioru ocen | 1,512 s |
| Pobranie i indeksowanie IMDb | 7,646 s |
| Nowa seria równoległa, maks. 6 pracowników (3 tytuły) | 23,305 s |
| Iloraz czasów obu prób | 2,28× |

Filmweb odpytuje wyszukiwarkę, podglądy i strony nawet pięciu kandydatów dla wariantu tytułu, a następnie VOD. W starej implementacji żądania każdej kolejnej pozycji czekały na wszystkie poprzednie tytuły. Odstęp 1,1 s powiększał ten koszt. Przy pierwszym odczycie oceny IMDb dochodzi import całego zbioru, obejmujący pobranie, rozpakowanie, walidację i indeks SQLite.

Nowa implementacja wykonuje ograniczoną liczbę tytułów jednocześnie (domyślnie 6, regulacja 1–16). Nie tworzy jednego wątku dla każdego pliku. Pracownicy współdzielą stan indeksu IMDb, informację o niedostępnej stronie IMDb, ograniczenie rozpoczynania żądań na host co 0,2 s i pomiary. Każdy posiada własne połączenie SQLite i klientów HTTP. Baza działa w WAL. Pobranie i import IMDb oraz pamiętanie nieudanego pobrania są synchronizowane dla całej serii.

Czasy są obserwacją dwóch prób, nie gwarancją. Zmiany odpowiedzi, blokady serwisów, rozmiar listy, opóźnienia sieci i stan pamięci wpływają na wynik. Sumy czasu etapów w próbie równoległej nakładają się; czasu oczekiwania kilku pracowników na jeden import nie można traktować jako kilku pobrań. Bezpośrednie API TMDB sprawdzono testami z kontrolowanymi odpowiedziami HTTP, bez aktywnego tokenu użytkownika.

Szczegółowe dane lokalnej próby: `build/profile-baseline.json`, `build/profile-baseline.log`, `build/profile-parallel.json`. Nie trafiają do Git. Pomiary każdej nowej serii są dodatkowo zapisywane w errors.log jako `moviecheck.performance`. Oddzielają czas odpowiedzi HTTP od limitowania żądań oraz pobieranie od indeksowania IMDb.

## Powtórzenie

W katalogu projektu uruchom (macOS):

```sh
.venv/bin/python -m scripts.profile_search --workers 1 --output build/proba1.json
.venv/bin/python -m scripts.profile_search --workers 6 --output build/proba6.json
```

Na Windows użyj `.\.venv\Scripts\python.exe`. Bez `--input` skrypt korzysta z powyższych trzech tytułów. Własną listę podaj przez `--input lista.txt --limit 10`. Wybierz nowe nazwy wyjściowe, jeśli chcesz oddzielne zimne pamięci; powtórzenie z tym samym plikiem wykorzysta poprzedni cache. Skrypt wysyła rzeczywiste żądania i nie generuje HTML.

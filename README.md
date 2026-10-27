# MovieCheck

Okienkowa aplikacja w Pythonie i PySide6 (Qt) do tworzenia katalogu filmów na podstawie nazw plików. Kod jest przeznaczony dla Windows i macOS; bieżąca weryfikacja została wykonana na Windows.

## Funkcje

- Wybór katalogu z filmami, opcjonalnie wraz z podkatalogami, albo listy `.txt`.
- Odczyt prostych list nazw, typowego `ls -l` i tabelarycznego wyniku PowerShell `ls`.
- Obsługa UTF-8, UTF-16 z BOM i awaryjnie Windows-1250.
- Rozpoznawanie tytułu i roku; usuwanie typowych oznaczeń jakości, kodeków i wydania.
- Wyszukiwanie najpierw w Filmweb, a przy braku opisu lub wyniku próba IMDb.
- Podgląd wyników, poprawianie tytułu i roku oraz ręczne wskazanie linku do filmu.
- Pobieranie w osobnym wątku, postęp i anulowanie z raportem częściowym.
- Lokalna pamięć danych SQLite ważna przez 7 dni, którą można wyłączyć.
- Samodzielny raport HTML z tytułem będącym linkiem, ocenami, gatunkami, krótkim opisem i źródłami. Raport nie pobiera zewnętrznych zasobów i działa po zapisaniu bez Internetu.

## Wymagania i instalacja

Wymagany Python 3.11 lub nowszy, z obsługiwaną przez PySide6 wersją systemu i architekturą. Dostęp do Internetu jest potrzebny podczas instalacji i pobierania danych.

Windows, PowerShell, w katalogu projektu:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m moviecheck
```

Po instalacji aplikację można otwierać także dwuklikiem `start_windows.cmd`. W środowisku, w którym przygotowano projekt, `.venv` jest już utworzone i ma zainstalowane zależności.

macOS, Terminal, w katalogu projektu:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m moviecheck
```

Opcjonalnie `chmod +x start_macos.command` pozwala używać przygotowanego pliku startowego. Środowiska `.venv` nie przenosi się między systemami; na każdym komputerze należy utworzyć własne.

## Przygotowanie listy TXT

Najpewniejszy format to jedna pełna nazwa pliku w wierszu, z rozszerzeniem, np. `Inception.2010.1080p.mkv`. Przykład znajduje się w `examples/lista.txt`.

macOS:

```sh
ls -1 /sciezka/do/filmow > lista.txt
```

Windows, PowerShell:

```powershell
Get-ChildItem 'D:\Filmy' -File -Name | Set-Content lista.txt -Encoding utf8
```

Typowy wynik `ls > plik.txt` w PowerShell jest obsługiwany, ale terminal może skrócić zbyt długie nazwy. Pełnej nazwy utraconej przy eksporcie nie da się odtworzyć. Listy wielokolumnowe i nazwy zawierające znak nowego wiersza nie są obsługiwane. Pliki bez rozpoznanego rozszerzenia wideo są pomijane.

## Obsługa

1. Wybierz katalog albo TXT. Opcję podkatalogów ustaw przed wyszukiwaniem.
2. Sprawdź tytuły i lata w tabeli. Przyciskiem „Popraw tytuł / rok…” skorygujesz zaznaczony wiersz.
3. W razie potrzeby zmień miejsce zapisu raportu.
4. Kliknij „Wyszukaj wszystkie filmy”. Raport zapisuje się automatycznie po zakończeniu.
5. Gdy dopasowanie jest niejednoznaczne lub błędne, zaznacz wiersz i wybierz „Wskaż link filmu…”. Aplikacja pobierze dane wskazanego filmu i odświeży raport.
6. „Otwórz raport” otwiera HTML w domyślnej przeglądarce. „Zapisz raport” pozwala zapisać obecne wyniki ponownie, np. w innym miejscu po błędzie zapisu.

Domyślne nazwy: `lista.txt` → `lista.html` obok listy; katalog `Filmy` → `Filmy.html` obok katalogu. Istniejący raport wymaga potwierdzenia zastąpienia. Pliki filmów i lista wejściowa nie są modyfikowane.

Anulowanie czeka na zakończenie bieżącego żądania HTTP (limit czasu sieci do 20 sekund bezczynności). Niezakończone wyszukiwanie zostaje oznaczone jako raport częściowy. Przy próbie zamknięcia działającego wyszukiwania aplikacja rozpoczyna anulowanie i prosi o ponowne zamknięcie po zakończeniu żądania.

## Źródła danych i ograniczenia

Filmweb: wyszukiwanie korzysta z publicznego endpointu używanego przez stronę `/api/v1/live/search`, a podgląd filmu z `/api/v1/film/{id}/preview` pozwala zbudować jego adres. Opis, gatunki i ocena pochodzą z mikrodanych HTML lub JSON-LD strony filmu. Nie jest to gwarantowane ani wersjonowane publiczne API dla aplikacji zewnętrznych; zmiany witryny mogą wymagać aktualizacji adaptera. Próba na żywo 2026-10-27 potwierdziła wyszukanie i pobranie opisu oraz oceny filmu „Incepcja (2010)”.

IMDb: adapter przeszukuje odnośniki stron filmów i odczytuje ich JSON-LD. Próba na żywo 2026-10-27 w tym środowisku zakończyła się pustą odpowiedzią HTTP 202 dla strony filmu i wyszukiwarki. Dlatego działanie pełnego uzupełniania danych z IMDb nie zostało potwierdzone; aplikacja jawnie zapisuje ten błąd w uwagach wyniku. Adapter nie omija blokad, CAPTCHA ani logowania. [Warunki korzystania z danych IMDb](https://help.imdb.com/article/imdb/general-information/can-i-use-imdb-data-in-my-software/G5JTRESSHJBBHTGX) ograniczają automatyczne pobieranie stron; dla stałej integracji należy ustalić odpowiedni dostęp do danych.

Opis z IMDb może być po angielsku; aplikacja nie tłumaczy fabuły. Znane angielskie gatunki są tłumaczone na polskie nazwy. Gdy Filmweb zawiera opis, IMDb nie jest odpytywane, więc raport nie zawsze zawiera obie oceny. Źródła ocen, gatunków i opisu są oznaczone osobno. Brak danych nie jest zastępowany wymyśloną treścią.

Przy dopasowywaniu sprawdzanych jest do pięciu wyników. Tytuł polski lub oryginalny musi być dostatecznie podobny, a dostępny rok zgodny. Zbliżone wyniki wymagają ręcznego wskazania linku. Program wykonuje żądania kolejno, w odstępach co najmniej 1,1 s w obrębie dostawcy; nie ponawia automatycznie blokad 403/429.

Lokalna pamięć wyników znajduje się w systemowym katalogu danych aplikacji MovieCheck. Usunięcie pliku `movies.sqlite3` przy zamkniętej aplikacji czyści pamięć. Nazwy plików są przetwarzane lokalnie, a do serwisów trafiają zapytania z tytułem i ewentualnym rokiem; same pliki wideo nie są wysyłane.

## Testy i diagnostyka

Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\check_sources.py
.\.venv\Scripts\python.exe scripts\build_example.py --screenshot
```

macOS: użyj `.venv/bin/python` i ukośników `/` w ścieżkach.

Testy jednostkowe i test przepływu okna Qt działają bez sieci. Test okna uruchamia Qt w trybie `offscreen`; pobieranie jest w nim zastąpione kontrolowanymi danymi testowymi. Skrypty diagnostyczne wykonują rzeczywiste żądania sieciowe. `build_example.py` tworzy raport `build/lista.html`, lokalną pamięć przykładu i opcjonalnie `build/app-preview.png`. Katalog `build/` nie jest wersjonowany.

## Struktura i rozwój

- `moviecheck/app.py` — okno Qt i wątek wyszukiwania.
- `moviecheck/inputs.py` — odczyt wejścia i rozpoznawanie nazw.
- `moviecheck/providers.py` — adaptery Filmweb/IMDb oraz dopasowanie filmów.
- `moviecheck/service.py` — kolejność źródeł i uzupełnianie braków.
- `moviecheck/cache.py` — pamięć SQLite.
- `moviecheck/report.py`, `moviecheck/templates/report.html` — raport HTML.
- `tests/` — testy bez dostępu do sieci.

Dokumentacja i komunikaty są po polsku, identyfikatory w kodzie po angielsku. Zależności i punkt wejścia `moviecheck` definiuje `pyproject.toml`.

Możliwe dalsze pakowanie: `pyside6-deploy run.py`. Wydania należy budować i sprawdzać osobno na Windows i macOS. Podpisane instalatory oraz testy na macOS nie zostały jeszcze przygotowane. [Dokumentacja dystrybucji Qt for Python](https://doc.qt.io/qtforpython-6/deployment/index.html).

Instrukcje pracy znajdują się w `AGENTS.md`, a historia współpracy w `docs/INTERACTIONS.md`.

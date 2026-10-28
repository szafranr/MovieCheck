# MovieCheck

Okienkowa aplikacja w Pythonie i PySide6 (Qt) do tworzenia katalogu filmów na podstawie nazw plików. Kod jest przeznaczony dla Windows i macOS; bieżąca weryfikacja została wykonana na Windows.

## Funkcje

- Wybór katalogu z filmami, opcjonalnie wraz z podkatalogami, albo listy `.txt`; filmy mogą być opisane nazwą pliku lub katalogu bez rozszerzenia.
- Odczyt prostych list nazw, typowego `ls -l` i tabelarycznego wyniku PowerShell `ls`.
- Obsługa UTF-8, UTF-16 z BOM i awaryjnie Windows-1250.
- Rozpoznawanie tytułu i roku; usuwanie typowych oznaczeń jakości, kodeków i wydania.
- Niezależne wyszukiwanie w Filmweb, IMDb i TMDB, z osobną oceną każdego serwisu. Opis z Filmweb ma pierwszeństwo.
- Dostępność VOD w Polsce: tylko abonamenty, z logotypami platform i linkami do ofert; bez wypożyczeń i zakupu.
- Podgląd wyników, poprawianie tytułu i roku oraz ręczne wskazanie linku do filmu.
- Równoległe wyszukiwanie tytułów (domyślnie 6 zadań, regulacja 1–16), postęp i anulowanie. Osobny krok generowania raportu z bieżącej kolejności tabeli.
- Lokalna pamięć SQLite: dane filmów i ocen do 7 dni, dostępność VOD do 6 godzin; bufor wyników można wyłączyć.
- Raport HTML z klikalną okładką po lewej, tytułem będącym linkiem, ocenami, gatunkami, krótkim opisem i źródłami po prawej. Tekst działa po zapisaniu bez Internetu; okładki są ładowane z adresów źródłowych i wymagają połączenia z siecią.

## Wymagania i instalacja

Wymagany Python 3.11 lub nowszy, z obsługiwaną przez PySide6 wersją systemu i architekturą. Dostęp do Internetu jest potrzebny podczas instalacji i pobierania danych.

Przy pierwszym odczycie niezależnej oceny IMDb aplikacja może pobrać oficjalny zbiór `title.ratings.tsv.gz` (około 9 MB według próby z 2026-10-27) i przygotować lokalny indeks SQLite. Ta operacja trwa dłużej niż zwykłe wyszukiwanie, a postęp przygotowania jest opisany pod tabelą. Zbiór jest odświeżany najpóźniej po 7 dniach; kolejne oceny są odczytywane z lokalnego indeksu. Dane IMDb przeznaczone są do użytku osobistego i niekomercyjnego, zgodnie z [zasadami udostępniania IMDb](https://data.imdb.com/non-commercial-datasets/).

Windows, PowerShell, w katalogu projektu:

Jeśli `.venv` zostało już przygotowane, uruchom od razu aplikację — nie twórz środowiska ponownie:

```powershell
cd D:\Projekty\MovieCheck
.\.venv\Scripts\python.exe -m moviecheck
```

Poniższe kroki są potrzebne przy pierwszej instalacji na nowym komputerze. Polecenie `py` wymaga launchera Pythona. Jeśli nie jest rozpoznawane, ale `python --version` zwraca wersję 3.11 lub nowszą, zastąp pierwszą linię poleceniem `python -m venv .venv`. Jeśli żadne z tych poleceń nie uruchamia Pythona, trzeba najpierw zainstalować interpreter lub wskazać pełną ścieżkę do już zainstalowanego `python.exe`.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m moviecheck
```

Po instalacji aplikację można otwierać także dwuklikiem `start_windows.cmd`. W środowisku, w którym przygotowano projekt, `.venv` jest już utworzone i ma zainstalowane zależności.

macOS, Terminal, po `git clone`, w katalogu projektu:

```sh
sh start_macos.command
```

Skrypt wymaga, aby `python3 --version` wskazywał Python 3.11 lub nowszy. Przy pierwszym uruchomieniu tworzy lokalne `.venv`, aktualizuje w nim `pip`, instaluje aplikację i zależności z `pyproject.toml`, a następnie otwiera okno. Instalacja wymaga Internetu. Przy kolejnych uruchomieniach korzysta z tego samego środowiska; po zmianie wersji lub konfiguracji odświeża instalację. Błąd instalacji zatrzymuje uruchamianie i pozostawia komunikat w Terminalu. Skrypt działa również z katalogu ze spacjami w nazwie.

`.venv` celowo nie znajduje się w Git: zawiera pliki zależne od systemu, architektury i lokalnych ścieżek. `git clone` pobiera kod i deklarację zależności, a skrypt odtwarza środowisko na nowym komputerze. Nie kopiuj `.venv` z Windows na Maca. Jeśli taki katalog już skopiowano, zachowaj go pod inną nazwą przed uruchomieniem skryptu.

Po przygotowaniu środowiska możesz też uruchamiać program bez instalowania:

```sh
.venv/bin/python -m moviecheck
```

Alternatywnie pierwszą instalację można wykonać ręcznie:

```sh
python3 --version  # wymagane co najmniej 3.11
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/python -m moviecheck
```

Błąd „setup.py or setup.cfg not found” przy obecnym `pyproject.toml` i starym `pip 21.2.4` wymaga aktualizacji pip powyższym poleceniem. Jeśli `.venv/bin/python --version` pokazuje mniej niż 3.11, najpierw zainstaluj nowszego Pythona i utwórz nim nowe środowisko; aktualizacja pip nie zmienia wersji interpretera.

Przykład przejścia z Pythona 3.9.6 na 3.12, jeśli na Macu masz Homebrew ([formuła Python 3.12](https://formulae.brew.sh/formula/python@3.12)):

```sh
brew install python@3.12
cd /Users/robert/Projekty/MovieCheck
mv .venv ".venv-python39-$(date +%s)"
python3.12 -m venv .venv
.venv/bin/python --version
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/python -m moviecheck
```

Zachowane stare środowisko jest wyłącznie kopią lokalną — nie dodawaj go do Git. Nie trzeba zmieniać systemowego Pythona ani domyślnego `python3`; nowe `.venv` korzysta z jawnie wybranego `python3.12`. Bez Homebrew można zainstalować Python 3.12 lub 3.13 z [oficjalnych instalatorów macOS](https://www.python.org/downloads/macos/) i użyć odpowiedniego polecenia wersji do utworzenia `.venv`.

 Plik `start_macos.command` ma w Git uprawnienie wykonywania i zakończenia linii LF; można go otworzyć również dwuklikiem w Finderze.

## Przygotowanie listy TXT

Najpewniejszy format to jedna nazwa pliku lub katalogu filmowego w wierszu, np. `Inception.2010.1080p.mkv`, `Final.Interview.2026.1080p.SCREENER.WEB-DL.H264.AAC-AOC` albo `Matchbox The Movie 2026 1080p WEB-DL HEVC x265`. Rozszerzenie wideo nie jest wymagane. Obsługiwane są również proste tytuły, np. `Inception`, ścieżki oraz nazwy zakończone `/` lub `\`. Przykłady znajdują się w `examples/`.

macOS:

```sh
ls -1 /sciezka/do/filmow > lista.txt
```

Windows, PowerShell:

```powershell
Get-ChildItem 'D:\Filmy' -Name | Set-Content lista.txt -Encoding utf8
```

Typowy wynik `ls > plik.txt` w PowerShell jest obsługiwany, również dla katalogów bez kolumny rozmiaru. Odczytywane są też katalogi w listingu Unix `ls -l`. Terminal może skrócić zbyt długie nazwy; pełnej nazwy utraconej przy eksporcie nie da się odtworzyć. Listy wielokolumnowe i nazwy zawierające znak nowego wiersza nie są obsługiwane. Pomijane są nagłówki, komentarze, napisy, grafiki, dokumenty, archiwa i inne znane pliki pomocnicze. Wpis bez rozszerzenia może być tytułem lub nazwą wydania filmu; nieznaną końcówkę po kropce, np. `.H264-GROUP`, traktuje się jako część nazwy, a nie dowód obecności rozszerzenia pliku.

Podczas skanowania dysku aplikacja rozpoznaje również katalogi filmowe po nazwie z rokiem lub oznaczeniem wydania. Taki katalog stanowi jedną pozycję, także jeśli zawiera kilka plików wideo; jego wnętrze nie jest ponownie dodawane do raportu. Wybranie bezpośrednio takiego katalogu pozwala rozpoznać tytuł nawet przy ogólnej nazwie pliku w środku, np. `video.mkv`. Katalog bez roku może zostać rozpoznany na podstawie zgodnej nazwy pliku wideo; w takim przypadku rok jest pobierany z tego pliku, jeśli jest jednoznaczny.

Katalogi zawierające kolejne katalogi filmowe są traktowane jako kolekcje; ich przeglądanie wymaga zaznaczenia „Uwzględnij podkatalogi”. Katalogi techniczne, np. `Samples`, `Subs`, `BDMV` i `CERTIFICATE`, oraz ukryte wpisy są pomijane przy skanowaniu. Dowiązania symboliczne nie są przeglądane. Jeśli TXT zawiera jednocześnie nazwę katalogu oraz plik rozpoznany jako ten sam tytuł i rok, zachowywany jest wpis pliku. Osobne pliki różnych wydań oraz różne lata produkcji pozostają oddzielnymi pozycjami.

## Obsługa

1. Wybierz katalog albo TXT. Opcję podkatalogów ustaw przed wyszukiwaniem.
2. Sprawdź rozpoznane tytuły i lata. W razie potrzeby użyj „Popraw tytuł / rok…”. Wpisz token lub klucz API TMDB w polu nad tabelą, jeśli chcesz pobierać trzecie oceny i okładki TMDB.
3. Wybierz liczbę równoległych zadań (domyślnie 6) i kliknij „1. Wyszukaj dane”. Program zbiera dane; nie zapisuje ani nie nadpisuje HTML na tym etapie.
4. Po komunikacie o zakończeniu kliknij nagłówek tytułu, roku lub jednej z trzech ocen, aby posortować tabelę. Kolejne kliknięcie zmienia kierunek; oceny są sortowane liczbowo, a brak oceny to odrębna wartość poniżej zera.
5. Kliknięcie podkreślonego tytułu otwiera stronę filmu: Filmweb, jeśli ma opis, w przeciwnym razie IMDb z opisem lub TMDB z opisem; przy braku opisów pozostaje pierwsza dostępna strona. Ręczny link Filmweb/IMDb/TMDB może poprawić dopasowanie także po sortowaniu.
6. Wybierz miejsce HTML i kliknij „2. Wygeneruj raport”. Zapisana lista odpowiada dokładnie bieżącej kolejności wierszy. Nadpisanie istniejącego pliku wymaga potwierdzenia dopiero na tym etapie.
7. „Otwórz raport” otwiera zapisany HTML w przeglądarce. Po kolejnych zmianach danych lub sortowania wygeneruj go ponownie.

Domyślne nazwy: `lista.txt` → `lista.html` obok listy; katalog `Filmy` → `Filmy.html` obok katalogu. Istniejący raport wymaga potwierdzenia zastąpienia. Pliki filmów i lista wejściowa nie są modyfikowane.

Okładka w raporcie jest linkiem do strony filmu u dostawcy obrazu. Aplikacja wybiera przede wszystkim okładkę TMDB w rozmiarze w500, a przy jej braku Filmweb lub IMDb; a pliku obrazu nie zapisuje lokalnie ani nie osadza w HTML. Plakat znajduje się po lewej stronie pozycji, na wysokość jej treści, z szerokością wynikającą z proporcji źródłowego obrazu. Na wąskich ekranach jego szerokość jest ograniczana, aby tekst pozostał czytelny; obraz zachowuje proporcje i nie jest przycinany. Mały skrypt w raporcie aktualizuje rozmiar po załadowaniu obrazu, zmianie szerokości okna i rozwinięciu uwag. Brak adresu lub błąd ładowania obrazu pozostawia sam tekst.

Starsze wpisy lokalnej pamięci, które nie zawierają jeszcze pola okładki, są uzupełniane podczas kolejnego wyszukiwania. Jeśli serwis jest wtedy niedostępny, zachowywane są dotychczasowe opisy i oceny.

W tabeli i raporcie zawsze są trzy osobne pozycje ocen: Filmweb, IMDb i TMDB. Brak oceny jednego źródła nie powoduje zastąpienia jej oceną drugiego. Błąd VOD nie usuwa pobranych ocen ani opisów.

Sekcja „Dostępny w abonamencie · Polska” pojawia się tylko po potwierdzeniu ofert abonamentowych Filmweb. Logotyp i nazwa platformy są linkiem do oferty filmu. Uwzględniane są aktywne oferty z płatnością oznaczoną jako subskrypcja; gdy Filmweb nie podaje ceny pojedynczego filmu, wymagane są jawne dane abonamentu platformy. Jawne wypożyczenie, zakup lub darmowa oferta bez subskrypcji nie są uznawane za abonament. Oferty nieaktywne, wygasłe i zaplanowane na przyszłość są pomijane. Abonamenty kanałów w innych platformach, np. SkyShowtime w Prime Video lub HBO w Canal+, są oznaczone „Dodatkowy abonament / pakiet”; nie oznaczają dostępu w podstawowym planie Prime lub Canal+.

Przy ofertach podana jest data sprawdzenia. Filmweb VOD jest odpytywany dla znalezionego filmu, a nie na podstawie ogólnej listy platform. Brak sekcji nie jest gwarancją niedostępności — może oznaczać brak znalezionego filmu w Filmweb lub błąd odczytu, widoczny w uwagach wyniku. Dostępność może się zmieniać. Logo, podobnie jak plakat, wymaga dostępu do Internetu; nazwa platformy pozostaje widoczna także bez obrazu.

Anulowanie czeka na zakończenie bieżącego żądania lub odebranie fragmentu odpowiedzi (limit bezczynności sieci wynosi 20 sekund dla stron i 30 sekund podczas pobierania zbioru IMDb). Import bazy także sprawdza żądanie anulowania. Niezakończone wyszukiwanie zostaje oznaczone jako raport częściowy. Przy próbie zamknięcia działającego wyszukiwania aplikacja rozpoczyna anulowanie i prosi o ponowne zamknięcie po zakończeniu żądania.

Błąd jednego źródła nie blokuje pozostałych źródeł tego filmu. Nieoczekiwany błąd przetwarzania pojedynczego filmu zostaje zapisany w jego uwagach, a wyszukiwanie przechodzi do następnego pliku. Po sprawdzeniu całej listy raport zawiera zarówno znalezione dane, jak i pozycje wymagające sprawdzenia. Błąd filmu nie powoduje oznaczenia całego raportu jako częściowego, jeśli sprawdzono wszystkie pozycje.

Jeśli błąd uniemożliwi pracę całej serii, np. nie uda się otworzyć pamięci danych, aplikacja pozostawia dotychczasowe wyniki i uwagi w tabeli oraz pokazuje komunikat o przerwaniu. Raport częściowy generuje użytkownik w drugim kroku. Gdy zapis HTML jest niemożliwy, wyniki pozostają w tabeli i można wybrać inne miejsce oraz ponowić „2. Wygeneruj raport”.

Nieoczekiwane błędy są zapisywane z nazwą pliku, źródłem i śladem wywołań w `errors.log`, obok `movies.sqlite3`. Na Windows jest to zwykle `%LOCALAPPDATA%\MovieCheck\MovieCheck\errors.log`. Dziennik ma limit 2 MB i dwie kopie rotacyjne. Brak dostępu do pliku diagnostycznego nie blokuje wyszukiwania. Daty VOD są porównywane bez konwersji przez systemowe znaczniki czasu, dzięki czemu wartości takie jak `9999-12-31` nie wywołują błędu Windows `OSError: [Errno 22] Invalid argument`.

## Źródła danych i ograniczenia

Filmweb: wyszukiwanie korzysta z publicznego endpointu używanego przez stronę `/api/v1/live/search`, a podgląd filmu z `/api/v1/film/{id}/preview` pozwala zbudować jego adres. Opis, gatunki i ocena pochodzą z mikrodanych HTML lub JSON-LD strony filmu. Nie jest to gwarantowane ani wersjonowane publiczne API dla aplikacji zewnętrznych; zmiany witryny mogą wymagać aktualizacji adaptera. Próba na żywo 2026-10-27 potwierdziła wyszukanie i pobranie opisu oraz oceny filmu „Incepcja (2010)”.

IMDb: adapter korzysta z publicznych podpowiedzi tytułów IMDb do rozpoznania identyfikatora i roku. Ocenę pobiera ze strony filmu, jeśli jest ona dostępna, a przy odmowie dostępu z oficjalnego zbioru `title.ratings.tsv.gz`, identyfikując film po jego numerze IMDb. Dzięki temu odpowiedź HTTP 202 lub 403 strony nie blokuje odczytu niezależnej oceny. Zbiór nie zawiera opisów fabuły, więc uzupełnienie opisu IMDb nadal zależy od dostępności strony. Adapter nie omija blokad, CAPTCHA ani logowania. Źródło oceny jest opisane po wskazaniu jej w raporcie kursorem. [Dokumentacja danych IMDb](https://data.imdb.com/non-commercial-datasets/).

Opis z IMDb może być po angielsku; aplikacja nie tłumaczy fabuły. Znane angielskie gatunki są tłumaczone na polskie nazwy. IMDb jest odpytywane również wtedy, gdy Filmweb zawiera już opis i ocenę. Ręczne wskazanie linku w dowolnym serwisie zachowuje próbę znalezienia pozostałych źródeł. Źródła ocen, gatunków i opisu są oznaczone osobno. Brak danych nie jest zastępowany wymyśloną treścią.

Przy dopasowywaniu sprawdzanych jest do pięciu wyników dla wariantu zapytania. Apostrofy proste i typograficzne są pomijane w porównaniu: `Bettys Revenge`, `Betty's Revenge` i `Betty’s Revenge` są równoważne. Pozostała interpunkcja nadal rozdziela słowa. Tytuł polski lub oryginalny musi być dostatecznie podobny, a dostępny rok zgodny. Zbliżone wyniki wymagają ręcznego wskazania linku.

Gdy pierwsze zapytanie nie daje dopasowania, wyszukiwarki otrzymują także pomocnicze warianty: z ujednoliconym apostrofem, bez apostrofu lub z apostrofem przed końcowym `s` wyrazu, np. `Bettys` → `Betty's`. Ten ostatni wariant jest heurystyką, a nie automatyczną zmianą tytułu. Sprawdzane są maksymalnie cztery unikalne warianty; pierwszy prawidłowy wynik kończy wyszukiwanie. Kontrola roku i niejednoznaczności pozostaje aktywna. Nie są przy tym dodawane ani usuwane słowa tytułu.

Program przetwarza tytuły równolegle. Każdy pracownik zachowuje odstęp co najmniej 1,1 s między żądaniami danego adaptera Filmweb/IMDb; dodatkowo wspólny limit dopuszcza rozpoczęcie żądania na dany host najwyżej co 0,2 s. Błędy dostępu i pusta odpowiedź HTTP 202 nie są ponawiane jako warianty zapisu tytułu; w przypadku IMDb ocenę można nadal odczytać z oficjalnego zbioru danych. Niejednoznaczny wynik wymaga ręcznego dopasowania. Zmiana zapisu tytułu nie rozwiązuje blokady odczytu opisu ze strony IMDb.

W podpowiedziach IMDb wynik z potwierdzonym rokiem ma pierwszeństwo przed tytułem bez roku. Skrócona nazwa wyświetlana przez IMDb, np. „Glass Onion” zamiast „Glass Onion: A Knives Out Mystery”, jest dopuszczana wyłącznie przy identycznym tytule głównym przed dwukropkiem i znanym, zgodnym roku. Tytuł główny musi mieć co najmniej 8 znaków po normalizacji; nie jest stosowane dowolne usuwanie słów. Kilka równie dobrych wyników nadal wymaga wskazania właściwego linku.

Lokalna pamięć wyników i indeks ocen IMDb znajdują się w pliku `movies.sqlite3` w systemowym katalogu danych aplikacji MovieCheck. Usunięcie tego pliku przy zamkniętej aplikacji czyści pamięć oraz indeks, który zostanie ponownie pobrany, gdy będzie potrzebny. Wyłączenie bufora omija zapisane rekordy filmów i VOD oraz odświeża zbiór ocen IMDb raz na serię wyszukiwania, jeśli jest on potrzebny. Nazwy plików są przetwarzane lokalnie, a do serwisów trafiają zapytania z tytułem i ewentualnym rokiem; same pliki wideo nie są wysyłane.

## TMDB: ocena, opis i okładka

Integracja korzysta z oficjalnego API TMDB. W ustawieniach API swojego konta TMDB uzyskaj API Read Access Token (Bearer) albo klucz v3 i wpisz go w polu aplikacji. Możesz również ustawić zmienną środowiskową `TMDB_READ_ACCESS_TOKEN` lub `TMDB_API_KEY` przed uruchomieniem. Pole jest maskowane; wartość nie jest zapisywana w QSettings, pamięci wyników, HTML ani pomiarach. Nie przesyłaj klucza w zgłoszeniu błędu.

Bez klucza pozostałe źródła działają; TMDB pokazuje brak oceny i uwagę o konfiguracji. Nie wpisujemy do kodu wspólnego klucza dystrybucyjnego. Ocena TMDB pochodzi z `vote_average` i jest pokazywana tylko przy co najmniej jednym głosie. Dopasowanie wykorzystuje identyfikator IMDb, jeśli go znamy, a w pozostałych przypadkach tytuł, warianty apostrofów i rok. Niejednoznaczne wyniki wymagają ręcznego linku. Polski opis ma pierwszeństwo przed angielskim opisem TMDB; opis Filmweb ma pierwszeństwo w całej aplikacji.

[Uwierzytelnianie TMDB](https://developer.themoviedb.org/docs/authentication-application), [wyszukiwanie](https://developer.themoviedb.org/reference/search-movie), [obrazy](https://developer.themoviedb.org/docs/image-basics). Logo pobrano bez modyfikacji z [oficjalnego zasobu TMDB](https://www.themoviedb.org/assets/2/v4/logos/v2/blue_square_2-d537fb228cf3ded904ef09b136fe3fec72548ebc1fea3fbbd1ad9e36364db38b.svg); jest umieszczone w sekcji źródeł i autorów oraz w stopce HTML wraz z wymaganym oznaczeniem. [Zasady oznaczania TMDB](https://developer.themoviedb.org/docs/faq).

## Wydajność i równoległość

Pomiar z 2026-10-28 dla Inception (2010), Interstellar (2014) i The Matrix (1999): dotychczasowe wyszukiwanie sekwencyjne 53,205 s, nowa próba równoległa 23,305 s, około 2,28× szybciej. Najwięcej czasu zajmował Filmweb: 41,929 s; pierwszy zbiór IMDb wymagał 7,646 s na pobranie i import. Są to dwie próby z rzeczywistymi serwisami i osobnymi pamięciami wyników, bez klucza TMDB; wahania sieci i liczba tytułów wpływają na wynik. [Pełny opis pomiaru](docs/PERFORMANCE.md).

Każdy pracownik ma własnych klientów HTTP i połączenie SQLite; WAL oraz limit oczekiwania 30 s pozwalają współdzielić lokalną pamięć bez przekazywania połączeń między wątkami. Indeks IMDb jest przygotowywany raz na serię, także przy wyłączonym buforze wyników. Błąd pobrania bazy jest pamiętany do końca serii. Anulowanie zatrzymuje podejmowanie kolejnych tytułów i czeka na trwające żądania.

Po każdej serii errors.log zawiera czas całkowity, liczbę pracowników i sumy czasu etapów pod nazwą `moviecheck.performance`. Etapy zachodzą na siebie, więc ich suma może przekraczać czas całkowity. Osobno mierzone są limity żądań, odpowiedzi HTTP, wyszukiwanie źródeł, VOD oraz pobranie i indeksowanie IMDb.

Pomiar własnej listy (wykonuje rzeczywiste żądania, zapisuje osobną bazę SQLite obok JSON):

```sh
.venv/bin/python -m scripts.profile_search --input lista.txt --limit 10 --workers 1 --output build/profile-serial.json
.venv/bin/python -m scripts.profile_search --input lista.txt --limit 10 --workers 6 --output build/profile-parallel.json
```

Na Windows zastąp `.venv/bin/python` przez `.\.venv\Scripts\python.exe`. Przy porównywaniu zimnej pamięci użyj nowych nazw plików wyjściowych. Diagnostyczny skrypt nie generuje HTML.

## Testy i diagnostyka

Log błędów na Windows znajduje się w `%LOCALAPPDATA%\MovieCheck\MovieCheck\errors.log`. W Eksploratorze można wkleić `%LOCALAPPDATA%\MovieCheck\MovieCheck` do paska adresu. Do zgłoszenia błędu dołącz `errors.log`, a jeśli istnieją, również `errors.log.1` i `errors.log.2` (rotacja: maksymalnie 2 MB na plik). Podaj wersję programu, tytuł filmu i przybliżoną godzinę błędu. Przed udostępnieniem sprawdź log pod kątem prywatnych ścieżek i nazw plików.


Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts\check_sources.py
.\.venv\Scripts\python.exe scripts\build_example.py --screenshot
.\.venv\Scripts\python.exe scripts\build_example.py --input moja-lista.txt --limit 3 --screenshot
```

macOS: użyj `.venv/bin/python` i ukośników `/` w ścieżkach.

Testy jednostkowe i test przepływu okna Qt działają bez sieci. Test okna uruchamia Qt w trybie `offscreen`; pobieranie jest w nim zastąpione kontrolowanymi danymi testowymi. Skrypty diagnostyczne wykonują rzeczywiste żądania sieciowe. `build_example.py` tworzy raport `build/lista.html`, lokalną pamięć przykładu i opcjonalnie `build/app-preview.png`. Katalog `build/` nie jest wersjonowany.

## Struktura i rozwój

- `moviecheck/app.py` — okno Qt i wątek wyszukiwania.
- `moviecheck/inputs.py` — odczyt wejścia i rozpoznawanie nazw.
- `moviecheck/providers.py` — adaptery Filmweb/IMDb oraz dopasowanie filmów.
- `moviecheck/service.py` — kolejność źródeł i uzupełnianie braków.
- `moviecheck/imdb.py` — rozpoznawanie tytułów IMDb i oficjalna baza ocen.
- `moviecheck/tmdb.py` — oficjalne API TMDB, oceny i plakaty.
- `moviecheck/performance.py` — wspólny stan serii, limity i pomiary.
- `moviecheck/vod.py` — weryfikacja abonamentów Filmweb dla Polski.
- `moviecheck/cache.py` — pamięć SQLite.
- `moviecheck/report.py`, `moviecheck/templates/report.html` — raport HTML.
- `tests/` — testy bez dostępu do sieci.

Dokumentacja i komunikaty są po polsku, identyfikatory w kodzie po angielsku. Zależności i punkt wejścia `moviecheck` definiuje `pyproject.toml`.

## Budowanie i dystrybucja

PyInstaller może dołączyć interpreter, biblioteki Qt i kod aplikacji do wydania uruchamianego na komputerze bez Pythona. Windows i macOS wymagają osobnych kompilacji, przygotowanych na odpowiednim systemie i dla właściwej architektury. [Opis działania PyInstaller](https://pyinstaller.org/en/stable/operating-mode.html).

Wspólnym punktem wejścia jest `build.py` — runner zadań podobny do Cake, napisany w Pythonie. Wymaga Pythona 3.11 lub nowszego. Sam tworzy oddzielne `.venv-build` i instaluje projekt z dodatkiem `.[build]` (PyInstaller i Pillow), korzystając z `uv`, jeśli jest dostępne, albo z `venv` i `pip`. Nie zmienia środowiska uruchomieniowego `.venv`. Instalacja narzędzi wymaga Internetu; przygotowane środowisko jest używane ponownie, dopóki nie zmieni się konfiguracja lub wersja.

| Zadanie | Działanie |
|---|---|
| `setup` | Przygotowanie środowiska budowania |
| `test` | Testy bez dostępu do sieci, z Qt w trybie offscreen |
| `icons` | Generowanie PNG, ICO i ICNS z wektorowej ikony |
| `build` | Testy → ikony → EXE/APP → weryfikacja gotowego programu |
| `release` | Zadanie `build` oraz plik wydania, manifest JSON i suma SHA-256 |
| `verify` | Ponowny test już zbudowanego EXE/APP |
| `version` | Wyświetlenie wersji, bez instalowania narzędzi |
| `bump` | Podniesienie wyłącznie trzeciego członu wersji, bez budowania |

Domyślne zadanie to `release`, a domyślny system `--target auto` wybiera system komputera. Próba zbudowania macOS na Windows lub odwrotnie kończy się czytelnym błędem przed instalowaniem środowiska.

### Windows — pojedynczy MovieCheck.exe

W PowerShell, w katalogu projektu:

```powershell
.\.venv\Scripts\python.exe build.py release --target windows
```

Program powstaje w `dist/windows/MovieCheck.exe`, a plik do przekazania odbiorcy w `dist/releases/`, np. `MovieCheck-0.1.10-windows-x64.exe`. Obok znajdują się manifest `.json` i plik `.sha256`. Numer w nazwie jest pobierany z kodu, a architektura z komputera budującego.

Pakiet zawiera ikonę, metadane wersji, szablon HTML, interpreter i biblioteki. Nie wymaga `.venv` ani źródeł na komputerze odbiorcy. Specyfikacja PyInstaller i pliki robocze powstają w `build/package/windows/`. Dodatkowe przykłady użycia: `build.py test`, `build.py build`, `build.py verify --target windows`.

Tryb `--onefile` rozpakowuje potrzebne biblioteki do katalogu tymczasowego przy uruchomieniu, więc start może trwać dłużej niż w wydaniu katalogowym. Pojedynczy plik programu nadal tworzy swoją pamięć SQLite i dziennik w systemowym katalogu danych użytkownika; raporty zapisuje w wybranym miejscu. Internet jest potrzebny do wyszukiwania, VOD, obrazów i pobrania zbioru ocen IMDb.

### macOS — aplikacja MovieCheck.app

Na Macu, przy użyciu Pythona 3.11 lub nowszego:

```sh
python3 build.py release --target macos
```

Oczekiwany wynik to `dist/macos/MovieCheck.app` oraz ZIP w `dist/releases/`, np. `MovieCheck-0.1.10-macos-arm64.zip`. Finder pokazuje APP jako jedną aplikację, chociaż technicznie jest to pakiet katalogów. ZIP jest przygotowywany systemowym `ditto`, z zachowaniem struktury i dowiązań pakietu. Wersja trafia do `Info.plist`, a ikona do pakietu ICNS. PyInstaller odradza łączenie `--onefile` i `--windowed` dla macOS; stosowany jest `--onedir`. [Dokumentacja pakietów macOS](https://pyinstaller.org/en/stable/usage.html#building-macos-app-bundles).

### Weryfikacja pakietu

Runner zatrzymuje budowanie po błędzie zadania. Po utworzeniu EXE/APP uruchamia gotowy program z `--self-test` w oddzielnym, pustym katalogu i bez ustawień ścieżek Pythona z komputera budującego. Na Windows skrypt ogranicza również ścieżkę wyszukiwania DLL podczas pakowania i testu, aby biblioteki innych programów z `PATH` nie trafiły do wydania. Test jest bez sieci: sprawdza uruchomienie Qt, ikonę, odczyt nazwy bez rozszerzenia, działanie SQLite, inicjalizację trzech klientów HTTPS z weryfikacją TLS oraz współbieżną obsługę SQLite, dołączony szablon raportu oraz zgodność wersji. Jeśli dystrybucja Pythona zawiera dodatkowy plik CA `codex-rejected-cas.pem` wymagany przez jej moduł SSL, runner dołącza go do pakietu. Wynik trafia do `build/package/<system>/smoke.json`, a testowy raport obok. Dopiero udana weryfikacja pozwala wykonać `release` i przygotować pliki z sumą kontrolną.

Gałąź macOS wymaga uruchomienia na rzeczywistym Macu; jej konfiguracja ma testy struktury specyfikacji, ale nie zastępuje to testu aplikacji na macOS. Podpisywanie wydania, notaryzacja Apple i instalatory nie są częścią tego runnera.

## Publikowanie w GitHub Releases

Pełna instrukcja krok po kroku: [Publikowanie wydań](docs/PUBLISHING.md).

Pliki z `dist/releases/` dołącza się jako załączniki wydania GitHub, bez dodawania ich do Git. Wydania repozytorium: [MovieCheck Releases](https://github.com/szafranr/MovieCheck/releases).

1. Wybierz zatwierdzony commit i numer wersji, np. `0.1.13`. Wyślij odpowiednie commity do GitHub (`git push origin main`, jeśli wydajesz main). Windows i Mac muszą budować ten sam commit i wersję.
2. Na Windows uruchom `.\.venv\Scripts\python.exe build.py release --target windows`, a na Macu `.venv/bin/python build.py release --target macos`.
3. Otwórz Releases → Draft a new release. W Choose a tag wpisz `v0.1.13`, wybierz Create new tag i ustaw Target na wydawany commit. Możesz wcześniej zapisać szkic, aby zebrać oba pakiety przed publikacją.
4. Ustaw tytuł `MovieCheck 0.1.13`, opisz zmiany i dołącz pliki z `dist/releases/`: EXE Windows, ZIP macOS oraz odpowiadające im manifesty JSON i sumy SHA-256. Przykładowe nazwy: `MovieCheck-0.1.13-windows-x64.exe` i `MovieCheck-0.1.13-macos-arm64.zip`. Budowa na Macu Intel otrzyma inną architekturę w nazwie; pojedynczy build nie obejmuje automatycznie obu architektur Maca.
5. Zapisz szkic przez Save draft albo opublikuj gotowy zestaw przez Publish release. Dla wersji testowej można zaznaczyć Pre-release. Odbiorcy pobierają programy z sekcji Assets; automatyczne Source code ZIP/TAR zawierają źródła.

Nie łącz pod jednym tagiem starego EXE `0.1.11` z paczką macOS `0.1.13`: przebuduj oba z tej samej wersji. Samo budowanie ani publikacja istniejącego kodu nie podnosi wersji. Tag wskazuje konkretny stan kodu, z którego pochodzą paczki.

Zadanie `release` w build.py przygotowuje pliki lokalnie; nie publikuje ich na GitHub. Publikację można później zautomatyzować przez GitHub Actions, uruchamiając runner osobno na Windows i macOS po dodaniu tagu. Taki workflow nie jest jeszcze częścią repozytorium.

Źródło instrukcji interfejsu: [GitHub — zarządzanie wydaniami](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

## Wersja, ikona i zakończenie wyszukiwania

Punktem początkowym jest `0.1.10`. Wersja ma dokładnie trzy człony `0.1.x`; kolejne iteracje zmieniające działanie aplikacji podnoszą tylko `x`, raz przed końcowym commitem. Jedynym źródłem jest `__version__` w `moviecheck/__init__.py`. Z tej wartości korzystają metadane pakietu Python, pasek tytułu, stopka raportu, metadane EXE/APP i nazwy plików wydania.

```powershell
.\.venv\Scripts\python.exe build.py version
.\.venv\Scripts\python.exe build.py bump
```

`bump` zmienia np. `0.1.10` na `0.1.11`, zachowując `0.1`. Samo ponowne budowanie, testy i zmiany wyłącznie dokumentacji nie zwiększają numeru.

Ikona przedstawia jasną klatkę filmową na granatowym tle, z turkusową lupą i znacznikiem sprawdzenia. Źródło wektorowe znajduje się w `moviecheck/assets/moviecheck.svg`, a PNG używane przez okno w `moviecheck/assets/moviecheck.png`. Zadanie `icons` odtwarza PNG oraz generuje ICO dla Windows i ICNS dla macOS w `build/icons/`. [Podgląd ikony](moviecheck/assets/moviecheck.png).

Po zakończeniu wyszukiwania pojawia się komunikat z liczbą sprawdzonych pozycji i wyników oraz instrukcją sortowania i wygenerowania HTML w drugim kroku. Anulowanie ma osobny komunikat częściowy. Błąd serii lub zapisu ma komunikat błędu. HTML powstaje wyłącznie po wybraniu „2. Wygeneruj raport”.

Instrukcje pracy znajdują się w `AGENTS.md`, a historia współpracy w `docs/INTERACTIONS.md`.

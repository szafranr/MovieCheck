# Dziennik interakcji i prac

## 2026-10-27 — Filmy opisane nazwą katalogu bez rozszerzenia

### Polecenie użytkownika

> aplikacja nie uwzględnia sytuacji, jak plik z filmem znajduje się w katalogu, czyli bez rozszerzenia pliku z filmem. taki przykład jest w examples

### Diagnoza i zmiany

- Użyto CodeGraph przed analizą `load_queries`, `extract_listing_names` i `parse_filename`; odczytano również instrukcje, dokumentację i rzeczywiste listy w `examples/`.
- Stwierdzono, że filtr TXT przyjmował wyłącznie wiersze zakończone rozszerzeniem wideo. Pomijane były m.in. `Final.Interview.2026.1080p.SCREENER.WEB-DL.H264.AAC-AOC`, `Mayday.2026.1080p.WEB.h264-ETHEL` oraz zapis z odstępami `Matchbox The Movie 2026 1080p WEB-DL HEVC x265 10Bit DDP5.1 Subs KINGDOM`.
- TXT przyjmuje teraz także nazwy katalogów i tytuły bez rozszerzenia, w tym kropki w nazwie wydania, ścieżki i końcowe separatory. Nadal pomijane są znane rozszerzenia pomocnicze, ukryte wpisy i foldery techniczne. Poprawiono rozpoznawanie sum listingu, aby nagłówek `total 10` był pomijany, ale film `Total Recall (1990)` pozostał przyjęty.
- Dodano wiersze katalogów PowerShell bez kolumny długości oraz katalogi w listingu Unix `ls -l`; zachowywane są nazwy zaczynające się od liczby, np. `1984 (1984)`.
- Skanowanie dysku uwzględnia katalogi nazwane filmem z rokiem lub oznaczeniem wydania. Katalog filmu jest jedną pozycją i nie dubluje znajdujących się w nim plików, także przy rekurencji. Kontenery kolekcji pozostają zależne od opcji podkatalogów. Katalog bez roku może wykorzystać rok z pliku o zgodnym tytule. Katalog wybrany bezpośrednio także może opisać film, nawet jeśli jego plik ma ogólną nazwę `video.mkv`.
- W liście obejmującej katalog i plik tego samego tytułu oraz roku zachowywany jest plik; oddzielne pliki wydań i różne roczniki są zachowane. Nie jest wykonywane przybliżone łączenie różnych tytułów.
- Uzupełniono README, w tym polecenie eksportu PowerShell obejmujące pliki i katalogi.

### Weryfikacja i zakończenie iteracji

- 78 testów zakończyło się sukcesem. Dodano 13 przypadków dla wpisów bez rozszerzeń z przykładów, mieszanych list i plików pomocniczych, wierszy katalogów PowerShell/Unix, ścieżek Windows/macOS, tytułów bez roku, duplikatów katalog/plik, różnych wydań, faktycznych katalogów filmowych i rekurencji. Zachowano wcześniejsze testy odporności wyszukiwania i generowania HTML.
- Sprawdzono wszystkie rzeczywiste listy bez wykonywania żądań sieciowych i bez zmiany plików: `177.txt` — 46 pozycji, w tym 14 bez rozszerzenia wideo; `178.txt` — 35 i 4; `179.txt` — 30 i 9; `180.txt` — 45 i 9; `lista.txt` — 48 i 9. Żaden tytuł z rozpoznanych wpisów nie został pominięty; identyczny tytuł i rok katalogu oraz pliku może dać jedną pozycję zgodnie z deduplikacją.
- Listy i raporty użytkownika w `examples/` oraz indeks `.codegraph/` pozostawiono poza commitem. Iterację kończy lokalny commit parsera, testów i dokumentacji, bez wysyłania do zdalnego repozytorium.

## 2026-10-27 — Błąd przy 80% i odporność całej serii wyszukiwania

### Zgłoszenie użytkownika

> mam błąd
> upewnij siuę, ze błąd sprawdzania jednego filmu nie zatrzyma wyszukiwania dla pozostałych.
> ten błąd mam juz drugi raz w tym samym miejscu 80% wyszukiwania, to przerywa generowania raportu html

Użytkownik dołączył zrzut z komunikatem `OSError: [Errno 22] Invalid argument` w oknie „Błąd wyszukiwania”.

### Potwierdzona przyczyna

- Przed analizą użyto CodeGraph do odczytu pętli wątku, kończenia wyszukiwania, obsługi dostawców i filtrowania ofert VOD.
- Odtworzono na Windows, że `datetime.fromisoformat(...).astimezone()` wywołuje `OSError: [Errno 22] Invalid argument` dla niektórych skrajnych dat, w tym `9999-12-31` i części dat sprzed 1970 r.
- Lokalną pamięć aplikacji otwarto wyłącznie do odczytu. Znaleziono konkretny wadliwy rekord: `/api/v1/vod/film/10044479/providers/list?countryCode=PL`, pole `end` o wartości `9999-12-31T00:00:00`.
- Wyjątek nie należał do dotychczas przechwytywanych typów w filtrze VOD ani w obsłudze źródeł. Trafiał do obsługi całej serii w wątku, a okno po takim błędzie pomijało generowanie HTML.

### Wykonane zmiany

- Daty ofert VOD są porównywane jako obiekty `datetime`, bez konwersji skrajnych dat przez systemowe funkcje czasu. Datom bez strefy przypisywana jest strefa odniesienia; jawne przesunięcia są zachowywane. Niepoprawna data pomija wyłącznie daną ofertę.
- Wyjątki pojedynczego dostawcy i VOD są przechwytywane niezależnie: pozostają w uwagach danego filmu, a poprawnie pobrane opisy i oceny zostają zachowane.
- Dodano dodatkową ochronę na poziomie każdego filmu w `SearchWorker`: nawet nieoczekiwany wyjątek całego `lookup` tworzy wynik z informacją o błędzie, zwiększa postęp i pozwala sprawdzić następny film. Nie przechwytywano `BaseException`; anulowanie pozostaje obsługiwane dotychczasową flagą.
- Okno zapisuje raport również po błędzie przerywającym serię, oznacza go jako częściowy i dopiero potem pokazuje komunikat o przerwaniu. Niesprawdzone pozycje otrzymują przyczynę przerwania. Gdy sam zapis nie jest możliwy, zebrane wyniki pozostają w tabeli.
- Zabezpieczono zamykanie zasobów, aby błąd jednego zasobu nie pomijał zamknięcia pozostałych i nie ukrywał zebranych wyników.
- Dodano `moviecheck/diagnostics.py`: nieoczekiwane wyjątki wraz z nazwą pliku, źródłem i śladem wywołań trafiają do `errors.log` w katalogu danych aplikacji. Limit: 2 MB i dwie kopie rotacyjne. Niepowodzenie otwarcia dziennika nie blokuje programu.
- Uzupełniono polskie README o kontynuowanie wyszukiwania, raporty częściowe, diagnostykę i obsługę skrajnych dat.

### Weryfikacja i zakończenie iteracji

- 65 testów zakończyło się sukcesem. Nowe regresje obejmują skrajne daty i poprawną ofertę po wadliwej, błąd źródła/VOD z zachowaniem drugiej oceny, błędy `OSError` oraz `TypeError` dokładnie po ośmiu z dziesięciu filmów, przetworzenie ostatniego filmu i zapis kompletnego HTML, raport częściowy zapisany przed komunikatem, błąd zamykania zasobu oraz zapis diagnostyki i brak uprawnień do dziennika.
- Końcowa kontrola rzeczywistej pamięci aplikacji w trybie tylko do odczytu przetworzyła oferty 17 filmów bez żadnego wyjątku. Wcześniej wadliwy rekord `10044479` poprawnie zwrócił jedną ofertę abonamentową Amazon Prime Video. Nie było potrzeby kasowania pamięci ani pobierania danych ponownie.
- Nie zmieniano list użytkownika `examples/lista.txt`, `examples/180.txt` ani indeksu `.codegraph/`. Iterację kończy lokalny commit poprawki, testów i dokumentacji, bez wysyłania do repozytorium zdalnego.
- Użytkownik powinien zamknąć i ponownie uruchomić aplikację, aby załadować poprawione moduły Pythona.

## 2026-10-27 — Abonamenty VOD i dwie niezależne oceny

### Polecenie użytkownika

> w serwisie filmweb jest informacja, czy dany film jest dostępny w VOD. Dodaj sprawdzanie tego i jak jest dostępny, to dodaj taka informację do sprawdzanego filmu, ale tylko jak jest w ramach subskrypcji, a nie wypożyczenia. moga to być małe loga netflix, prime, skyhowtime, appleTV itd.
> dodaj niezalezne oceny z filmweb i imdb (dwie pozycje)

### Ustalenia na podstawie rzeczywistych źródeł

- Użyto CodeGraph przed analizą modeli, parserów, logiki źródeł, raportu i okna Qt. Dodatkowo odczytano pliki, których CodeGraph nie zwrócił w komplecie.
- Sprawdzono publiczną stronę Filmweb `/film/Incepcja-2010-500891/vod` oraz jej żądania w izolowanej przeglądarce. Oferty filmu pochodzą z `/api/v1/vod/film/{id}/providers/list?countryCode=PL`, a metadane platform i logotypy z `/api/v1/vod/providers/list?countryCode=PL`.
- Filmweb jawnie oznacza w płatnościach `subscription`, `rent`, `buy` i `free`. Część ofert abonamentowych, np. HBO Max, nie ma osobnej płatności za film, ale platforma ma pole `abonaments` z cenami abonamentu. Dostępność nie może być wnioskowana z samej nazwy platformy ani z listy wszystkich dostawców w stopce strony.
- Bezpośrednie strony IMDb nadal zwracają odmowę dostępu lub pustą odpowiedź. Potwierdzono natomiast działanie publicznych podpowiedzi tytułów IMDb i dostępność oficjalnego `https://datasets.imdbws.com/title.ratings.tsv.gz` o rozmiarze 8 721 264 bajtów w chwili sprawdzenia. Dokumentacja: `https://data.imdb.com/non-commercial-datasets/`.

### Wykonane zmiany

- Dodano `VodOffer`, `VodAvailability` i moduł `moviecheck/vod.py`. Wybierane są aktywne, niewygasłe i już rozpoczęte oferty dla Polski. Wymagana jest jawna subskrypcja w płatności albo brak osobnej płatności oraz potwierdzony, dodatni abonament platformy. Wypożyczenia, zakup, darmowe oferty bez subskrypcji i nierozpoznane typy nie są promowane do abonamentów.
- Logotyp i nazwa platformy prowadzą do oferty filmu. Abonamenty kanałów w innych platformach są opisane jako dodatkowy abonament/pakiet, a nie dostęp w podstawowym planie. Raport pokazuje datę sprawdzenia i kraj. Oferty są buforowane do 6 godzin, metadane platform do 7 dni. Błąd odczytu VOD nie usuwa opisów ani ocen.
- Zmieniono wyszukiwanie na niezależne sprawdzanie Filmweb i IMDb, również gdy pierwszy serwis ma już opis. W raporcie zawsze są dwie pozycje ocen, a w Qt osobne kolumny Filmweb i IMDb oraz kolumna VOD. Brak oceny nie jest zastępowany oceną innego serwisu.
- Dodano `moviecheck/imdb.py`: rozpoznawanie identyfikatora przez podpowiedzi IMDb oraz awaryjny odczyt oceny z oficjalnego zbioru IMDb. Zbiór jest pobierany strumieniowo, importowany partiami do indeksu SQLite i odświeżany do 7 dni; anulowanie lub błędne dane nie zastępują poprzedniej bazy. Niedostępność pobierania nie powoduje ponawiania całego zbioru dla każdego filmu. Okno pokazuje komunikaty przygotowania bazy.
- Bufor pojedynczego filmu nie wydłuża świeżości zbioru ocen IMDb. Wyłączenie bufora odświeża potrzebny zbiór raz na serię wyszukiwania. Rekord z samym identyfikatorem IMDb i bez rozpoznanego tytułu nie nadpisuje późniejszego, poprawnego rozpoznania.
- W IMDb potwierdzony rok ma pierwszeństwo przed wynikiem bez roku. Dodano ostrożną obsługę skróconego tytułu przed dwukropkiem (np. Glass Onion), wymagając identycznego tytułu głównego, co najmniej 8 znaków i znanego, zgodnego roku. Nadal odrzucane są niejednoznaczne wyniki, seriale i odcinki.
- W raporcie zamieszczono wymagane wskazanie IMDb jako źródła i informację o osobistym, niekomercyjnym użyciu danych. README opisuje pierwsze pobranie, źródła, ograniczenia opisów IMDb, okresy pamięci oraz zasady abonamentów.
- Skrypty diagnostyczne dostosowano do nowego dostawcy IMDb. Generator przykładu przyjmuje osobną listę `--input` i ograniczenie `--limit`, aby weryfikować krótki zestaw bez zmieniania list użytkownika.

### Weryfikacja

- 57 testów zakończyło się sukcesem: zachowane testy wejścia, tytułów, plakatów i raportu oraz nowe przypadki abonamentów, wykluczenia płatności, dat i kraju, odświeżania VOD, niezależności ocen, awarii źródeł, podpowiedzi i aliasów IMDb, importu/anulowania/świeżości bazy i całego przepływu Qt. Sprawdzenie składni modułów zakończyło się bez błędów.
- Próba na żywo potwierdziła obie oceny i abonamenty: „Glass Onion” — Filmweb 6,6 i IMDb 7.1, Netflix; „Incepcja” — Filmweb 8,2 i IMDb 8.8, HBO Max oraz dodatkowy abonament HBO w Canal+; „Wąwóz / The Gorge” — Filmweb 6,2 i IMDb 6.7, Apple TV. Wypożyczenia obecne w odpowiedzi Filmweb nie trafiły do raportu.
- W Edge sprawdzono faktyczne załadowanie wszystkich logotypów i plakatów, dwie liczbowe oceny przy każdym filmie, proporcje i położenie plakatów oraz brak błędów JavaScript. Kontrola wykryła początkowo rozszerzanie siatki na wąskim ekranie; poprawiono szerokość kolumny i zawijanie nazw ofert. Końcowy test dla 390 px nie wykazał przewijania poziomego.
- Obejrzano końcowy zrzut `build/report-posters.png`. Aktualny raport z rzeczywistymi wynikami znajduje się w `build/lista.html`; podgląd Qt w `build/app-preview.png`. Dane i skrypty pomocnicze w `build/` nie są wersjonowane.
- Podczas pracy pojawiły się zmiany użytkownika w `examples/lista.txt` oraz plik `examples/180.txt`. Pierwsza diagnostyka wczytała rozszerzoną listę; zatrzymano wyłącznie własny proces diagnostyczny i dalsze próby wykonano na osobnym `build/validation-vod.txt`. Zmiany list użytkownika i `.codegraph/` pozostawiono poza commitem.
- Iterację kończy lokalny commit kodu, testów, skryptów diagnostycznych i dokumentacji, bez wysyłania do zdalnego repozytorium.

## 2026-10-27 — Okładki po lewej stronie raportu

### Polecenie użytkownika

> dodaj jeszcze okładkę filmu z lewej strony, obrazek jako link.
> okładka wysokości całego wiersza, szerokość dopasowana do źródła, tytuł i tekst od okładki

### Wykonane zmiany

- Przed analizą kodu użyto CodeGraph do odczytu modeli, parserów dostawców, generatora raportu i testów; następnie odczytano szablon HTML i aktualną dokumentację.
- Do `MovieData` dodano opcjonalny `poster_url`. Filmweb pobiera adres z Open Graph lub mikrodanych obrazu, a IMDb/JSON-LD obsługuje adres tekstowy, obiekt ImageObject i listę obrazów oraz zapasowo Open Graph.
- Adresy plakatów są sprawdzane i ograniczone do HTTPS. Obrazy w raporcie korzystają z oryginalnych adresów źródłowych, bez lokalnego pobierania i osadzania binarnego.
- Raport ma okładkę po lewej jako link do strony filmu, a nazwę pliku, tytuł, oceny, gatunki, opis i uwagi po prawej. Wysokość treści wyznacza wysokość okładki, a jej naturalne proporcje szerokość. Na wąskim ekranie szerokość obrazu ograniczono do 38% pozycji, zachowując cały obraz bez przycinania i czytelność tekstu.
- Wprowadzono niewielki lokalny skrypt dostosowujący rozmiary po wczytaniu obrazu i zmianie rozmiaru treści. CSP dopuszcza ten skrypt przez losowy nonce oraz obrazy HTTPS, bez dopuszczania dowolnych skryptów. Brak lub błąd obrazu pozostawia treść tekstową.
- Starsze dane pamięci bez pola plakatu są odświeżane przy kolejnym pobraniu filmu; jeśli sieć jest niedostępna, aplikacja zachowuje wcześniej zapisane dane filmu.
- README uzupełniono o układ, obsługę starszej pamięci i wymaganie połączenia z siecią do wyświetlania obrazów. Tekst raportu pozostaje dostępny offline.

### Weryfikacja

- Wszystkie 32 testy zakończyły się sukcesem, w tym testy adresów obrazu i formatów JSON-LD, plakatu Filmweb, wyboru zapasowego plakatu z drugiego źródła, pomijania nieprawidłowych adresów i aktualizacji starszej pamięci z zachowaniem danych przy awarii sieci.
- Wygenerowano `build/lista.html` z rzeczywistymi plakatami trzech filmów: „Incepcja”, „Matrix” i „Życie jest piękne”.
- Sprawdzono raport w izolowanym Edge sterowanym przez Playwright: wszystkie trzy obrazy się załadowały, ich wysokość odpowiada wysokości wnętrza pozycji, szerokość zachowuje proporcje źródła, a tekst zaczyna się za obrazem. Nie odnotowano błędów JavaScript. Przy szerokości 390 px raport nie wychodzi poza ekran.
- Obejrzano zrzut `build/report-posters.png`; układ jest czytelny i odpowiada zamówieniu. Zrzut mobilny zapisano w `build/report-posters-mobile.png`. Pomocnicze skrypty i wyniki w `build/` nie są wersjonowane.
- Nie modyfikowano nieśledzonych `.codegraph/`, `tests/180.txt` ani `tests/180.html`. Iterację kończy lokalny commit kodu, szablonu, testów i dokumentacji, bez wysyłania do zdalnego repozytorium.

## 2026-10-27 — Tytuły bez apostrofu: Bettys Revenge

### Polecenie użytkownika

> aplikacja nie znalazła np filmu Bettys Revenge, a ja znajduje go w imdb https://www.imdb.com/title/tt38984885/
> popraw algorytm żeby uwzględniał również skrócony zapis bez apostrofu, bo chyba w tym był problem

### Diagnoza i zmiany

- Przed analizą kodu użyto istniejącego indeksu CodeGraph do odczytu normalizacji tytułów, wyszukiwania, odczytu nazw plików, logiki źródeł i testów.
- Odczytano zgłoszony wpis z dostarczonych lokalnie plików `tests/180.txt` i `tests/180.html`. Nazwa pliku jest rozpoznawana jako `Bettys Revenge`, rok 2026. Raport zawiera brak dopasowania Filmweb oraz pustą odpowiedź IMDb HTTP 202. To potwierdzona przyczyna braku danych IMDb; samego braku apostrofu nie uznano za dowiedzioną przyczynę.
- Wyszukiwarka internetowa potwierdziła stronę IMDb filmu „Betty's Revenge (2026)”, identyfikator `tt38984885`; bezpośredni odczyt tej strony narzędziem internetowym zakończył się HTTP 403.
- W normalizacji apostrofy proste, typograficzne i ich typowe zamienniki są usuwane zamiast zamieniane na spację. Warianty `Bettys Revenge`, `Betty's Revenge` i `Betty’s Revenge` osiągają identyczne dopasowanie. Zachowano rozdzielanie słów inną interpunkcją i normalizację polskich znaków.
- Dodano maksymalnie cztery unikalne warianty zapytania dla obu dostawców, używane dopiero po braku dopasowania poprzedniego: oryginał, ujednolicony apostrof, brak apostrofu oraz pomocniczy apostrof przed końcowym `s` wyrazu. Tytuł użytkownika nie jest przy tym zmieniany.
- Zachowano progi podobieństwa, kontrolę roku i odrzucanie niejednoznacznych wyników. Błędy dostępu oraz HTTP 202 nie powodują ponawiania żądań z kolejnymi wariantami.
- Zaktualizowano polską dokumentację działania algorytmu i jego ograniczeń.

### Weryfikacja i zakończenie iteracji

- Pełny zestaw 27 testów zakończył się sukcesem, w tym 7 nowych testów regresji: zapis z różnymi apostrofami i bez nich, rok i niejednoznaczność, limit wariantów, próby w obu wyszukiwarkach, zakończenie po pierwszym wyniku i brak ponawiania pustej odpowiedzi HTTP 202.
- Próba na rzeczywistej nazwie pliku potwierdziła współczynnik dopasowania `1.0` do „Betty's Revenge (2026)”. Końcowa próba na żywo wykazała dwa kolejne zapytania Filmweb: `Bettys Revenge`, a następnie `Betty's Revenge`. Drugie znalazło film o tytule „Betty's Revenge”, roku 2026, z opisem i oceną, pod adresem `https://www.filmweb.pl/film/Betty%27s+Revenge-2026-10125167`. Zapisano raport `build/bettys-revenge.html` na podstawie rzeczywistych danych.
- Osobna próba bezpośredniego pobrania `https://www.imdb.com/title/tt38984885/` nadal zakończyła się pustą odpowiedzią HTTP 202. Błąd IMDb pozostaje ograniczeniem dostępu; w tym przypadku poprawka umożliwia znalezienie danych w Filmweb bez przechodzenia do IMDb.
- Nie zmieniano ani nie dodawano do commita nieśledzonych `.codegraph/`, `tests/180.txt` i `tests/180.html`.
- Iterację kończy lokalny commit kodu, testów, README i dziennika, bez wysyłania zmian do zdalnego repozytorium.

## 2026-10-27 — Nierozpoznane polecenie `py`

### Zgłoszenie użytkownika

Użytkownik uruchomił `py -3 -m venv .venv`; PowerShell zgłosił, że `py` nie jest rozpoznawanym poleceniem.

### Ustalenia i zmiany

- Potwierdzono obecność `.venv\Scripts\python.exe` i jego działanie: Python 3.12.14. Nie ma potrzeby ponownego tworzenia istniejącego środowiska.
- Wskazano bezpośrednie uruchamianie `.venv\Scripts\python.exe -m moviecheck` lub plik `start_windows.cmd`.
- Uzupełniono README o rozróżnienie uruchamiania przygotowanej aplikacji i instalacji na nowym komputerze oraz alternatywę dla nieobecnego launchera `py`.
- Potwierdzono lokalne repozytorium Git na gałęzi `main`, śledzącej `origin/main`, oraz zdalne repozytorium `https://github.com/szafranr/MovieCheck.git`.
- W katalogu pojawiło się nieśledzone `.codegraph/`. Nie modyfikowano go ani nie dodawano do commita. Ta iteracja dotyczy dokumentacji, bez analizy i zmiany kodu.
- Iterację kończy lokalny commit obejmujący README i dziennik; wysyłanie zmian do zdalnego repozytorium nie jest częścią tej operacji.

## 2026-10-27 — Dodanie projektu do Git

### Polecenie użytkownika

> przypomnij jak dodać ten folder do git. repozytorium już założyłem

### Odpowiedź i zakres

- Przygotowano instrukcję dla PowerShell: przejście do `D:\Projekty\MovieCheck`, `git init -b main`, dodanie plików, pierwszy commit, dodanie `origin` i `git push -u origin main`.
- Użytkownik ma zastąpić przykładowy adres rzeczywistym adresem utworzonego repozytorium. Podana procedura zakłada puste repozytorium zdalne; przy istniejących plikach zdalnych trzeba najpierw uwzględnić ich historię.
- Wskazano, że `.gitignore` wyklucza `.venv`, `build`, pamięć SQLite i pliki środowiskowe.
- Zgodnie z prośbą o przypomnienie nie wykonywano inicjalizacji, dodawania zdalnego repozytorium, commita ani wysyłania zmian. Użytkownik nie podał adresu repozytorium i nie potwierdzono jeszcze lokalnej inicjalizacji Git.

## 2026-10-27 — Implementacja Python i Qt

### Polecenie użytkownika

> zrób taką aplikację na bazie python i qt

### Decyzje i wykonane zmiany

- Zaimplementowano aplikację okienkową Python 3.11+ / PySide6 (Qt Widgets), z zależnościami określonymi w `pyproject.toml`.
- Dodano odczyt katalogu i podkatalogów, list TXT UTF-8/UTF-16/Windows-1250 oraz typowych listingów Unix i PowerShell. Parser wydobywa tytuł i rok, usuwa oznaczenia wydania i zachowuje liczby będące częścią tytułu.
- Dodano tabelę wyników, korektę tytułu i roku, ręczne wskazanie adresu filmu, wątek wyszukiwania, postęp, anulowanie i ponowny zapis raportu.
- Dodano adaptery Filmweb i IMDb, ocenę podobieństwa tytułów i zgodności roku oraz jawne oznaczanie niejednoznacznych wyników.
- Filmweb wymaga publicznych wyników `/api/v1/live/search` zamiast odczytywania odnośników ze strony wyszukiwarki: HTML zawiera również rekomendacje, które nie są wynikami zapytania. Podgląd `/api/v1/film/{id}/preview` służy do utworzenia adresu zawierającego tytuł, rok i identyfikator. Strony filmu udostępniają obecnie mikrodane HTML, więc oprócz JSON-LD dodano parser tych pól.
- Przy braku opisu Filmweb aplikacja próbuje IMDb, zachowując osobne źródła ocen i opisu. Przy ręcznej korekcie Filmweb zapytanie uzupełniające bazuje na wskazanym filmie, a nie na pierwotnej błędnej nazwie.
- Dodano lokalną pamięć SQLite na 7 dni, sekwencyjne żądania z odstępem co najmniej 1,1 s na dostawcę i obsługę odmowy dostępu bez obchodzenia blokad.
- Dodano samodzielny raport HTML z listą rozszerzoną, linkami, ocenami, gatunkami, opisami i uwagami, trybem jasnym/ciemnym oraz stylem wydruku. Dane są escapowane, a zapis wykorzystuje plik tymczasowy i atomową podmianę.
- Dodano skrypty uruchamiania Windows/macOS, listę przykładową, diagnostykę źródeł i generator przykładowego raportu z podglądem Qt. Przepisano README jako instrukcję instalacji i obsługi po polsku.

### Środowisko i weryfikacja

- Standardowe uruchomienie powłoki i środowiska Node nadal nie działało z powodu błędu MXC dotyczącego `G:`. Uruchomienie powłoki poza wadliwym sandboxem pozwoliło odczytać i zweryfikować projekt; nie odrzucono automatycznej zgody na tę operację.
- Potwierdzono zapis istniejącej dokumentacji i brak zagnieżdżonych instrukcji. Katalog `.codegraph/` nie istnieje; CodeGraph pominięto.
- Potwierdzono, że `D:\Projekty\MovieCheck` nie jest repozytorium Git. Zgodnie z wcześniejszym ustaleniem nie inicjalizowano Git i nie wykonywano commita.
- Systemowe polecenie `python` prowadzi do aliasu Microsoft Store. Wykorzystano dostępny interpreter Python 3.12.14 z pakietu środowiska Codex i `uv` do utworzenia lokalnego `.venv`.
- Zainstalowano aplikację i zależności w `.venv`: między innymi PySide6 6.12.0, HTTPX 0.28.1, BeautifulSoup 4.15.0 i Jinja2 3.1.6.
- Polecenie `.venv\Scripts\python.exe -m unittest discover -s tests -v` zakończyło się sukcesem: 20 testów. Zakres: wejście i kodowania, rozpoznawanie nazw, mikrodane i JSON-LD, odrzucanie błędnych adresów i niejednoznacznych dopasowań, kolejność źródeł i korekta ręczna, pamięć SQLite, escapowanie i braki danych w HTML oraz cały przepływ Qt z kontrolowanymi odpowiedziami dostawcy.
- Próba na żywo potwierdziła bezpośrednie pobranie i automatyczne wyszukanie „Incepcji (2010)” wraz z opisem i oceną. Pierwsze próby ujawniły błędy formatu danych i adresów; poprawiono je przed końcową próbą.
- IMDb zwrócił pustą odpowiedź HTTP 202 zarówno dla strony filmu, jak i wyszukiwarki. To nadal ogranicza działanie uzupełniania danych na żywo; parser i logika przełączania źródeł mają testy kontrolowane. README jawnie opisuje ograniczenie i warunki dostępu do danych.
- `scripts/build_example.py --screenshot` znalazł dane dla wszystkich trzech przykładów: „Inception”, „The Matrix” i „Życie jest piękne”. Utworzono `build/lista.html` i `build/app-preview.png` z rzeczywistymi wynikami Filmweb.
- Obejrzano podgląd Qt. Pierwszy podgląd offscreen nie wykrył fontów Windows; generator podglądu uzupełniono o rejestrację systemowego fontu Segoe UI. Kolejny podgląd jest czytelny i ma poprawne polskie znaki.

### Otwarte kwestie

- Zweryfikować aplikację na rzeczywistym macOS i przygotować osobne podpisane wydania, jeśli użytkownik ich potrzebuje.
- Ustalić niezawodny, odpowiednio autoryzowany dostęp do danych IMDb; obecne środowisko nie otrzymuje treści stron.
- Po dodaniu projektu do Git kończyć każdą iterację ze zmianami commitem wraz z dokumentacją i dziennikiem.

## 2026-10-27 — Propozycja technologii

### Polecenie użytkownika

> zaproponuj aplikację, która będzie działać na windows i macos.
> ma na podstawie zawartości katalogu lub wskazanego pliku txt, który zawiera ls >plik.txt
> z nazwami plików z filmami. znaleźć opisy filmu, kategorie i ocenę.
> wyszukiwanie ma być na stronie filmweb.pl a jak nie ma opisu, to imdb.com.
> raport z wyszukiwania ma się znaleźć w pliku html <nazwa pliku lub katalogu>.html
> zawartość raportu w postaci listy rozszerzonej. nazwa filmu, ocena filmweb/imdb kategoria (dramat/komedia/horror itd) pod spodem krótki opis.
> nazwa filmu może być linkiem do filmweb/imdb
> na razie zaproponuj technologię dla aplikacji

### Decyzje, zmiany i weryfikacja

- Przygotowano rekomendację Python + PySide6, HTTPX, parser HTML, Jinja2 i SQLite; nie jest to jeszcze zatwierdzony wybór użytkownika.
- Uzupełniono README o nowe wymagania i propozycję technologii. Nie rozpoczęto implementacji.
- Sprawdzono oficjalną dokumentację Qt for Python, Tauri, HTTPX, Jinja i IMDb. Rekomendacja uwzględnia oddzielne adaptery dostawców, rozpoznawanie tytułu i roku oraz lokalną pamięć wyników.
- Zaznaczono różnice między `ls` w Unix i PowerShell oraz konieczność oznaczania źródła ocen i opisów.
- Nie potwierdzono stabilnego publicznego API Filmweb. Oficjalne zbiory IMDb nie obejmują opisów fabuły; sposób dostępu do opisów wymaga dalszego ustalenia.
- Ponowna próba sprawdzenia plików i Git w powłoce zakończyła się tym samym błędem MXC dotyczącym woluminu `G:`. Nie udało się sprawdzić stanu repozytorium ani wykonać commita. Narzędzie bezpośredniej edycji wykorzystano do aktualizacji dokumentacji.

### Następny krok

Uzyskać decyzję użytkownika dotyczącą technologii. Przed implementacją sprawdzić dostęp do danych Filmweb i IMDb oraz przykładowy rzeczywisty plik wejściowy.

Dziennik stanowi trwały kontekst dla użytkownika i kolejnych agentów AI. Każda iteracja powinna zawierać datę, polecenie użytkownika, decyzje, zmiany, wynik weryfikacji i dalsze kwestie. Sekrety i prywatny tok rozumowania nie są zapisywane.

## 2026-10-27 — Rozpoczęcie projektu

### Polecenie użytkownika

> zaczynamy nowy projekt do pobierania informacji o filmach na podstawie zawrtości katalogu lub pliku.txt z nazwami plików.
> zapisuj wszystkie interacje dla siebie i innych agentów AI
> w momencie jak dodam projekt do gi, to każda iteracja ma zakończyć się commit.
> dokumentacja aplikacji ma byc po polsku
> nazwy zmiennych, funkcji i procedur po angielsku

Użytkownik przekazał również zasadę korzystania z CodeGraph, gdy repozytorium zawiera `.codegraph/`, i wskazał katalog projektu `D:\Projekty\MovieCheck`.

### Decyzje i zmiany

- Przyjęto nazwę projektu MovieCheck zgodną z nazwą katalogu.
- Przygotowano `README.md` z celem, wymaganiami i kwestiami do ustalenia.
- Przygotowano `AGENTS.md` z zasadami językowymi, obowiązkiem prowadzenia dziennika, zasadą commitów po dodaniu Git oraz instrukcją CodeGraph.
- Nie wybrano jeszcze technologii, dostawcy danych ani interfejsu aplikacji.

### Weryfikacja i ograniczenia

- Próby uruchomienia powłoki nie powiodły się z powodu błędu programu uruchamiającego MXC dotyczącego nierozpoznanego systemu plików woluminu `G:`.
- Alternatywna próba odczytu katalogu przez środowisko Node zakończyła się nieoczekiwanym zamknięciem procesu.
- Nie udało się sprawdzić zawartości katalogu, obecności `.codegraph/` ani stanu Git. Nie wykonano commita ani testów aplikacji.
- Narzędzie bezpośredniej edycji zakończyło zapis trzech plików dokumentacji bez zgłoszenia błędu. Niezależny odczyt plików pozostaje niedostępny.

### Następny krok

Po przywróceniu dostępu do narzędzi potwierdzić zapis dokumentacji i stan katalogu oraz Git. Ustalić formę aplikacji i źródło metadanych przed implementacją.

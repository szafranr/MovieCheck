# Dziennik interakcji i prac

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

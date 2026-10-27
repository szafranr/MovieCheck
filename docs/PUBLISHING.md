# Publikowanie MovieCheck w GitHub Releases

## 1. Wybierz kod i wersję wydania

Publikuj oba systemy z tej samej wersji i tego samego commita. Przykłady poniżej używają `0.1.13`; sprawdź rzeczywisty numer przed każdym wydaniem.

Na komputerze z aktualnym kodem zatwierdź zmiany i wyślij je do repozytorium:

```sh
git status
git push origin main
git rev-parse HEAD
```

Zapisz pełny hash commita. Na drugim komputerze, w katalogu projektu, pobierz zmiany:

```sh
git switch main
git pull --ff-only
git rev-parse HEAD
```

Oba hashe muszą być identyczne. Jeśli masz niezapisane zmiany lub lokalne commity, uporządkuj je przed wydaniem; nie nadpisuj ich wymuszonym resetem. Gdy na main trwają dalsze prace, buduj z osobnego checkoutu wybranego commita.

Sprawdzenie wersji na Windows:

```powershell
.\.venv\Scripts\python.exe build.py version
```

Na macOS:

```sh
.venv/bin/python build.py version
```

Wersja pochodzi z `moviecheck/__init__.py`. Nie uruchamiaj `bump` osobno na każdym komputerze. Numer podnosimy raz na iterację zmieniającą działanie, zatwierdzamy go w Git, a dopiero potem budujemy oba systemy. Samo ponowne pakowanie nie zmienia numeru.

## 2. Zbuduj Windows

Na Windows, w katalogu projektu, ze środowiskiem przygotowanym według README:

```powershell
.\.venv\Scripts\python.exe build.py release --target windows
```

Zadanie przygotuje `.venv-build`, wykona testy, wygeneruje ikony, zbuduje EXE i sprawdzi gotowy pakiet. Pliki wydania pojawią się w `dist/releases/`:

- `MovieCheck-0.1.13-windows-x64.exe`
- `MovieCheck-0.1.13-windows-x64.sha256`
- `MovieCheck-0.1.13-windows-x64.json`

Nazwy mogą zawierać inną architekturę, jeśli budujesz na innym komputerze. Odbiorca otrzymuje EXE; `.venv` i źródła nie są potrzebne do uruchomienia pakietu.

## 3. Zbuduj macOS

Na Macu `.venv/bin/python --version` musi wskazywać co najmniej Python 3.11. Instalację i odtworzenie środowiska opisuje [README](../README.md).

```sh
.venv/bin/python build.py release --target macos
```

Pliki wynikowe:

- `dist/macos/MovieCheck.app` — lokalna aplikacja.
- `dist/releases/MovieCheck-0.1.13-macos-arm64.zip` — paczka do publikacji.
- Pliki o tej samej podstawie nazwy, z rozszerzeniami `.sha256` i `.json`.

`arm64` oznacza build dla Apple Silicon; budowa interpreterem x64 otrzyma oznaczenie `x64`. Jeden build nie tworzy automatycznie obu architektur. Do Releases przesyłaj ZIP przygotowany przez runner, który zachowuje strukturę APP i dowiązania.

Sprawdź uruchomienie:

```sh
open dist/macos/MovieCheck.app
```

Przed publikacją wykonaj także krótkie wyszukiwanie z małej listy i sprawdź wygenerowany HTML. Automatyczny test pakietu nie wykonuje żądań sieciowych. Runner nie konfiguruje podpisywania wydania ani notaryzacji Apple.

## 4. Utwórz szkic wydania na GitHub

1. Otwórz [MovieCheck — Releases](https://github.com/szafranr/MovieCheck/releases).
2. Wybierz **Draft a new release**.
3. W **Choose a tag** wpisz `v0.1.13`, a następnie **Create new tag**. Jeśli tag już istnieje, sprawdź, czy wskazuje commit użyty do buildów.
4. W **Target** wskaż dokładnie wydawany commit. Wybierając main, upewnij się, że jego bieżący commit nadal jest tym, z którego zbudowano paczki.
5. Wpisz tytuł `MovieCheck 0.1.13` i opis zmian. Możesz użyć **Generate release notes** i uzupełnić tekst.
6. W polu załączników dodaj EXE Windows, ZIP macOS oraz ich manifesty JSON i sumy SHA-256 z `dist/releases/`.
7. Wybierz **Save draft**, jeśli zbierasz jeszcze pliki z drugiego komputera.

Nie dodawaj buildów przez git add. Katalog `dist/` pozostaje ignorowany; paczki są załącznikami wydania. Nie mieszaj np. starego EXE 0.1.11 i ZIP 0.1.13 pod jednym tagiem. Wersje w nazwach, manifestach i aplikacjach muszą odpowiadać tagowi.

## 5. Opublikuj

Po zebraniu i sprawdzeniu obu paczek otwórz szkic. Jeśli wydanie jest testowe, zaznacz **Pre-release**. Kliknij **Publish release**. Przy niezmiennych wydaniach GitHub wszystkie załączniki muszą być gotowe przed publikacją.

Użytkownicy pobierają aplikację z sekcji **Assets**. Automatyczne pozycje **Source code (zip/tar.gz)** zawierają źródła i nie zastępują EXE ani aplikacji macOS.

Lokalne `build.py release` wyłącznie przygotowuje pliki. Nie tworzy tagów, nie wysyła kodu i nie publikuje na GitHub. Automatyzacja przez GitHub Actions nie jest jeszcze skonfigurowana.

## Diagnostyka budowania macOS

Aby zapisać pełny log, w tym stderr z testów i PyInstaller:

```sh
mkdir -p build
.venv/bin/python build.py release --target macos > build/build-macos.log 2>&1
```

Po błędzie prześlij końcową część logu oraz wynik `git rev-parse HEAD` i `build.py version`. Brak komunikatu „Wydanie:” oznacza, że bieżąca próba nie zakończyła przygotowania paczki; wcześniejsze pliki w dist mogą nadal istnieć.

Zgłoszony log z wersji 0.1.11 kończył się błędem testu `test_isolated_windows_run_excludes_foreign_dll_search_paths`. Test niepoprawnie dzielił ścieżkę Windows po dwukropku na POSIX. Poprawka dotyczy testu i zachowuje weryfikację izolacji bibliotek. Po pobraniu poprawki uruchom ponownie pełne `release`; nie pomijaj testów.

Źródło instrukcji GitHub: [Zarządzanie wydaniami](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository).

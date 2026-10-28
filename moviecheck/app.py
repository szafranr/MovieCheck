import sys
import logging
import os
import time
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, QThread, QUrl, Signal, Qt
from PySide6.QtGui import QDesktopServices, QIcon, QColor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QVBoxLayout, QWidget, QSpinBox,
)

from .cache import MovieCache
from . import __version__
from .diagnostics import configure_logging
from .inputs import load_queries, suggested_report_path
from .models import MovieQuery, MovieResult
from .providers import validate_movie_url
from .report import translate_genres, write_report
from .service import MovieService
from .performance import BatchState

logger = logging.getLogger(__name__)


class SearchWorker(QThread):
    result_ready = Signal(int, object)
    progress = Signal(int, int, str)
    failed = Signal(str)

    def __init__(self, jobs, cache_path: Path, use_cache: bool, parent=None, *, workers=6, tmdb_credential=""):
        super().__init__(parent)
        self.jobs = jobs
        self.cache_path = cache_path
        self.use_cache = use_cache
        self.workers = max(1, min(16, workers))
        self.tmdb_credential = tmdb_credential
        self.partial = True
        self.error = ""
        self.state = BatchState()
        self.elapsed = 0.0

    def run(self):
        started = time.perf_counter()
        queue = Queue()
        for job in self.jobs:
            queue.put(job)
        completed = 0
        lock = threading.Lock()
        initialization_lock = threading.Lock()
        stop = threading.Event()

        def cancelled():
            return self.isInterruptionRequested() or stop.is_set()

        def status(text):
            with lock:
                self.progress.emit(completed, len(self.jobs), text)

        def work():
            nonlocal completed
            cache = service = None
            try:
                with initialization_lock:
                    cache = MovieCache(self.cache_path, self.use_cache)
                cache.batch_state = self.state
                cache.tmdb_credential = self.tmdb_credential
                service = MovieService(cache, cancelled, status)
                while not cancelled():
                    try:
                        index, query, override = queue.get_nowait()
                    except Empty:
                        break
                    try:
                        result = service.lookup(query, override)
                    except Exception as error:
                        logger.exception("Błąd przetwarzania pliku %s", query.filename)
                        result = MovieResult(query, notes=[f"Błąd przetwarzania filmu: {type(error).__name__}: {error}"])
                    if cancelled():
                        break
                    with lock:
                        completed += 1
                        self.result_ready.emit(index, result)
                        self.progress.emit(completed, len(self.jobs), query.title)
            finally:
                for resource in (service, cache):
                    if resource is not None:
                        try:
                            resource.close()
                        except Exception as error:
                            logger.exception("Błąd zamykania zasobów wyszukiwania")
                            with lock:
                                self.error = self.error or f"{type(error).__name__}: {error}"

        def guarded_work():
            try:
                work()
            except Exception as error:
                logger.exception("Przerwanie serii wyszukiwania")
                with lock:
                    self.error = self.error or f"{type(error).__name__}: {error}"
                stop.set()

        try:
            with ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="moviecheck") as executor:
                futures = [executor.submit(guarded_work) for _ in range(min(self.workers, len(self.jobs)))]
                for future in futures:
                    future.result()
        except Exception as error:
            logger.exception("Błąd puli wyszukiwania")
            self.error = f"{type(error).__name__}: {error}"
        self.partial = cancelled() or bool(self.error) or completed < len(self.jobs)
        self.elapsed = time.perf_counter() - started
        self.state.log(self.elapsed, self.workers)
        if self.error:
            self.failed.emit(self.error)


class SortItem(QTableWidgetItem):
    def __init__(self, text, index, number=None):
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, index)
        self.number = number

    def __lt__(self, other):
        if self.column() in (2, 3, 4, 5):
            return (self.number if self.number is not None else -1) < (getattr(other, "number", None) if getattr(other, "number", None) is not None else -1)
        return self.text().casefold() < other.text().casefold()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"MovieCheck {__version__} — katalog filmów")
        self.setWindowIcon(QIcon(str(Path(__file__).with_name("assets") / "moviecheck.png")))
        self.resize(1180, 760)
        self.settings = QSettings("MovieCheck", "MovieCheck")
        self.source = None
        self.results = []
        self.worker = None
        self.report_path = None
        self.report_partial = False
        self.job_output = None
        self.completed_indices = set()
        self.search_done = False

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        heading = QLabel("MovieCheck")
        heading.setStyleSheet("font-size: 28px; font-weight: 700;")
        layout.addWidget(heading)
        caption = QLabel("Wybierz filmy. Pobierz informacje. Zapisz katalog HTML.")
        layout.addWidget(caption)

        input_row = QHBoxLayout()
        self.input_path = QLineEdit()
        self.input_path.setReadOnly(True)
        self.input_path.setPlaceholderText("Katalog z filmami lub lista plików .txt")
        self.directory_button = QPushButton("Wybierz katalog…")
        self.text_button = QPushButton("Wybierz TXT…")
        self.directory_button.clicked.connect(self.choose_directory)
        self.text_button.clicked.connect(self.choose_text)
        input_row.addWidget(self.input_path, 1)
        input_row.addWidget(self.directory_button)
        input_row.addWidget(self.text_button)
        layout.addLayout(input_row)

        options = QHBoxLayout()
        self.recursive = QCheckBox("Uwzględnij podkatalogi")
        self.recursive.toggled.connect(self.reload_source)
        self.use_cache = QCheckBox("Używaj pamięci wyników (oceny: 7 dni, VOD: 6 godz.)")
        self.use_cache.setChecked(True)
        options.addWidget(self.recursive)
        options.addWidget(self.use_cache)
        self.parallelism = QSpinBox()
        self.parallelism.setRange(1, 16)
        self.parallelism.setValue(6)
        self.parallelism.setPrefix("Równolegle: ")
        options.addWidget(self.parallelism)
        options.addStretch()
        layout.addLayout(options)
        tmdb_row = QHBoxLayout()
        tmdb_row.addWidget(QLabel("Token / klucz TMDB:"))
        self.tmdb_token = QLineEdit(os.environ.get("TMDB_READ_ACCESS_TOKEN", "") or os.environ.get("TMDB_API_KEY", ""))
        self.tmdb_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.tmdb_token.setPlaceholderText("Wpisz lokalnie — token nie jest zapisywany ani umieszczany w raporcie")
        tmdb_row.addWidget(self.tmdb_token)
        layout.addLayout(tmdb_row)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Raport HTML:"))
        self.output_path = QLineEdit()
        self.output_path.setReadOnly(True)
        self.output_button = QPushButton("Zmień miejsce…")
        self.output_button.clicked.connect(self.choose_output)
        output_row.addWidget(self.output_path, 1)
        output_row.addWidget(self.output_button)
        layout.addLayout(output_row)

        actions = QHBoxLayout()
        self.search_button = QPushButton("1. Wyszukaj dane")
        self.search_button.clicked.connect(self.start_all)
        self.cancel_button = QPushButton("Anuluj")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_search)
        self.correct_button = QPushButton("Popraw tytuł / rok…")
        self.correct_button.clicked.connect(self.correct_query)
        self.link_button = QPushButton("Wskaż link filmu…")
        self.link_button.clicked.connect(self.lookup_link)
        self.open_button = QPushButton("Otwórz raport")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_report)
        self.export_button = QPushButton("2. Wygeneruj raport")
        self.export_button.clicked.connect(self.export_report)
        for button in (self.search_button, self.cancel_button, self.correct_button, self.link_button, self.export_button, self.open_button):
            actions.addWidget(button)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Plik", "Tytuł ↗", "Rok", "Filmweb", "IMDb", "TMDB", "VOD — abonament", "Gatunki", "Stan"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(2, 60)
        self.table.setColumnWidth(3, 85)
        self.table.setColumnWidth(4, 85)
        self.table.setColumnWidth(5, 85)
        self.table.setColumnWidth(6, 180)
        self.table.setColumnWidth(7, 170)
        self.table.itemSelectionChanged.connect(self.show_details)
        self.table.itemClicked.connect(self.open_title_link)
        layout.addWidget(self.table, 1)
        self.details = QLabel("Wyniki niejednoznaczne można poprawić, wskazując link do właściwego filmu.")
        self.details.setWordWrap(True)
        # Treść z nazw plików i sieci zawsze jest zwykłym tekstem.
        from PySide6.QtCore import Qt
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.details)
        self.status = QLabel("Gotowe do wczytania listy filmów.")
        layout.addWidget(self.status)
        credits_row = QHBoxLayout()
        from PySide6.QtSvgWidgets import QSvgWidget
        logo = QSvgWidget(str(Path(__file__).with_name("assets") / "tmdb.svg"))
        logo.setFixedSize(52, 38)
        credits_row.addWidget(logo)
        self.attribution = QLabel('<a href="https://www.themoviedb.org/">Źródła i autorzy: TMDB</a> · This product uses the TMDB API but is not endorsed or certified by TMDB.')
        self.attribution.setWordWrap(True)
        self.attribution.setOpenExternalLinks(True)
        credits_row.addWidget(self.attribution, 1)
        layout.addLayout(credits_row)
        self.setCentralWidget(container)
        self.set_busy(False)

    def choose_directory(self):
        selected = QFileDialog.getExistingDirectory(self, "Wybierz katalog z filmami", self.settings.value("last_directory", ""))
        if selected:
            self.load_source(Path(selected))

    def choose_text(self):
        selected, _ = QFileDialog.getOpenFileName(self, "Wybierz listę plików", self.settings.value("last_directory", ""), "Lista plików (*.txt)")
        if selected:
            self.load_source(Path(selected))

    def reload_source(self):
        if self.source:
            self.load_source(self.source)

    def load_source(self, path: Path):
        try:
            queries = load_queries(path, self.recursive.isChecked())
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Nie można wczytać wejścia", str(error))
            return
        self.source = path
        self.settings.setValue("last_directory", str(path if path.is_dir() else path.parent))
        self.input_path.setText(str(path))
        self.output_path.setText(str(suggested_report_path(path)))
        self.results = [MovieResult(query, notes=["Nie uruchomiono wyszukiwania."]) for query in queries]
        self.completed_indices.clear()
        self.search_done = False
        self.report_path = None
        self.search_done = False
        self.table.setSortingEnabled(False)
        self.table.clearContents()
        self.table.setRowCount(len(queries))
        for index, result in enumerate(self.results):
            self.update_row(index, result)
        self.table.setSortingEnabled(True)
        self.table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.progress.setValue(0)
        self.status.setText(f"Wczytano {len(queries)} plików. Sprawdź rozpoznane tytuły i lata.")
        self.set_busy(False)

    def choose_output(self):
        selected, _ = QFileDialog.getSaveFileName(self, "Miejsce zapisu raportu", self.output_path.text(), "Raport HTML (*.html)")
        if selected:
            path = Path(selected)
            self.output_path.setText(str(path if path.suffix.lower() == ".html" else path.with_suffix(".html")))

    def start_all(self):
        self.start_jobs([(index, result.query, "") for index, result in enumerate(self.results)])

    def start_jobs(self, jobs):
        if not jobs or not self.source:
            return
        self.report_path = None
        self.search_done = False
        self.completed_indices.difference_update(index for index, _, _ in jobs)
        self.table.setSortingEnabled(False)
        cache_directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.worker = SearchWorker(jobs, cache_directory / "movies.sqlite3", self.use_cache.isChecked(), self, workers=self.parallelism.value(), tmdb_credential=self.tmdb_token.text().strip())
        self.worker.result_ready.connect(self.receive_result)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.search_finished)
        self.set_busy(True)
        self.worker.start()

    def receive_result(self, index: int, result: MovieResult):
        self.results[index] = result
        self.completed_indices.add(index)
        self.update_row(index, result)
        self.show_details()

    def update_progress(self, completed: int, total: int, title: str):
        self.progress.setMaximum(total)
        self.progress.setValue(completed)
        self.status.setText(f"Wyszukiwanie {completed}/{total}: {title}")

    def search_finished(self):
        worker = self.worker
        self.worker = None
        self.search_done = True
        if worker.error:
            for index, result in enumerate(self.results):
                if index not in self.completed_indices:
                    result.notes.append(f"Wyszukiwanie przerwane: {worker.error}")
                    self.update_row(index, result)
        self.report_partial = worker.partial or bool(worker.error) or len(self.completed_indices) < len(self.results)
        self.table.setSortingEnabled(True)
        self.set_busy(False)
        found = sum(bool(result.entries) for result in self.results)
        message = (f"Sprawdzono: {len(self.completed_indices)} z {len(self.results)} pozycji.\n"
                   f"Znaleziono dane: {found}.\n\nPosortuj tabelę klikając nagłówki, a następnie wybierz „2. Wygeneruj raport”.")
        self.status.setText(f"Wyszukiwanie zakończone. Z danymi: {found}. Posortuj tabelę i wygeneruj raport.")
        if worker.error:
            QMessageBox.warning(self, "Wyszukiwanie przerwane", worker.error + "\n" + message)
        else:
            heading = "Wyszukiwanie zakończone częściowo" if self.report_partial else "Wyszukiwanie zakończone"
            QMessageBox.information(self, heading, message)
        worker.deleteLater()

    def ordered_results(self):
        return [self.results[self.result_index(row)] for row in range(self.table.rowCount())]

    def result_index(self, row):
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else -1

    def save_report(self, output: Path, partial: bool) -> bool:
        try:
            write_report(output, self.source, self.ordered_results(), partial)
        except (OSError, ValueError) as error:
            self.status.setText("Nie udało się zapisać raportu. Wyniki pozostały w tabeli.")
            QMessageBox.warning(self, "Błąd zapisu raportu", str(error))
            return False
        self.report_path = output
        self.open_button.setEnabled(True)
        found = sum(bool(result.entries) for result in self.results)
        prefix = "Zapisano raport częściowy" if partial else "Zapisano raport"
        self.status.setText(f"{prefix}: {output} · Z danymi: {found}/{len(self.results)}")
        return True

    def export_report(self):
        if not self.source or self.worker is not None or not (self.search_done or self.completed_indices):
            return
        output = Path(self.output_path.text())
        if output.exists() and QMessageBox.question(self, "Zastąpić raport?", f"Zastąpić plik:\n{output}?") != QMessageBox.StandardButton.Yes:
            return
        self.save_report(output, self.report_partial or len(self.completed_indices) < len(self.results))

    def update_row(self, index: int, result: MovieResult):
        row = next((row for row in range(self.table.rowCount()) if self.result_index(row) == index), index)
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        movie = result.primary
        genres = next((entry.genres for entry in result.entries if entry.genres), [])
        ratings, numbers = [], {}
        for column, source in enumerate(("Filmweb", "IMDb", "TMDB"), 3):
            entry = result.entry_for(source)
            ratings.append(f"{entry.rating}/{entry.rating_scale}" if entry and entry.rating else "brak oceny")
            try:
                numbers[column] = float(entry.rating.replace(",", ".")) if entry and entry.rating else None
            except (ValueError, TypeError):
                numbers[column] = None
        year = (movie.year if movie else None) or result.query.year
        numbers[2] = year
        vod = ", ".join(offer.provider_name + (" (dodatkowy pakiet)" if offer.additional_subscription else "") for offer in result.vod.offers)
        values = [result.query.filename, movie.title if movie else result.query.title,
                  str(year or ""), *ratings, vod or ("brak ofert" if result.vod.checked_at else "—"),
                  translate_genres(genres), result.status if index in self.completed_indices else "Oczekuje"]
        for column, value in enumerate(values):
            item = SortItem(value, index, numbers.get(column))
            item.setToolTip("\n".join(result.notes) if column == 8 else value)
            if column == 1 and movie:
                item.setData(Qt.ItemDataRole.UserRole + 1, movie.url)
                font = item.font()
                font.setUnderline(True)
                item.setFont(font)
                item.setForeground(QColor("#247ac2"))
                item.setToolTip("Otwórz stronę filmu: " + movie.url)
            self.table.setItem(row, column, item)
        self.table.setSortingEnabled(sorting)

    def open_title_link(self, item):
        if item.column() != 1:
            return
        url = item.data(Qt.ItemDataRole.UserRole + 1)
        index = item.data(Qt.ItemDataRole.UserRole)
        movie = self.results[index].primary
        if url and movie:
            try:
                url = validate_movie_url(url, movie.source)
            except Exception:
                return
            QDesktopServices.openUrl(QUrl(url))

    def show_details(self):
        index = self.result_index(self.table.currentRow())
        if index < 0 or index >= len(self.results):
            return
        result = self.results[index]
        description = result.description_entry
        text = (f"{description.description}\nOpis: {description.source}" if description else "Brak opisu.")
        if result.notes:
            text += "\n" + "\n".join(result.notes)
        self.details.setText(text[:1800])

    def correct_query(self):
        index = self.result_index(self.table.currentRow())
        if index < 0:
            QMessageBox.information(self, "Wybierz film", "Najpierw zaznacz wiersz na liście.")
            return
        query = self.results[index].query
        title, accepted = QInputDialog.getText(self, "Popraw tytuł", "Tytuł filmu:", text=query.title)
        if not accepted or not title.strip():
            return
        year, accepted = QInputDialog.getText(self, "Popraw rok", "Rok produkcji (puste pole = dowolny):", text=str(query.year or ""))
        if not accepted:
            return
        if year.strip() and not (year.strip().isdigit() and 1800 <= int(year.strip()) <= 2100):
            QMessageBox.warning(self, "Niepoprawny rok", "Podaj rok od 1800 do 2100 lub pozostaw pole puste.")
            return
        self.results[index] = MovieResult(MovieQuery(query.filename, title.strip(), int(year.strip()) if year.strip() else None), notes=["Zmieniono zapytanie. Uruchom wyszukiwanie ponownie."])
        self.completed_indices.discard(index)
        self.update_row(index, self.results[index])
        self.show_details()
        self.status.setText("Zmieniono zapytanie. Raport wymaga ponownego wygenerowania.")

    def lookup_link(self):
        index = self.result_index(self.table.currentRow())
        if index < 0:
            QMessageBox.information(self, "Wybierz film", "Najpierw zaznacz wiersz na liście.")
            return
        result = self.results[index]
        url, accepted = QInputDialog.getText(self, "Wskaż właściwy film", "Pełny adres HTTPS filmu w Filmweb, IMDb lub TMDB:", text=result.primary.url if result.primary else "")
        if not accepted or not url.strip():
            return
        try:
            from urllib.parse import urlsplit
            hostname = urlsplit(url.strip()).hostname
            source = "Filmweb" if hostname in ("filmweb.pl", "www.filmweb.pl") else "TMDB" if hostname in ("themoviedb.org", "www.themoviedb.org") else "IMDb"
            url = validate_movie_url(url.strip(), source)
        except ValueError as error:
            QMessageBox.warning(self, "Niepoprawny adres", str(error))
            return
        except Exception as error:
            QMessageBox.warning(self, "Niepoprawny adres", str(error))
            return
        self.start_jobs([(index, result.query, url)])

    def cancel_search(self):
        if self.worker:
            self.worker.requestInterruption()
            self.cancel_button.setEnabled(False)
            self.status.setText("Anulowanie po zakończeniu bieżącego żądania sieciowego…")

    def set_busy(self, busy: bool):
        for control in (self.directory_button, self.text_button, self.recursive, self.use_cache, self.parallelism, self.tmdb_token):
            control.setEnabled(not busy)
        for control in (self.search_button, self.correct_button, self.link_button, self.output_button, self.export_button):
            control.setEnabled(not busy and bool(self.results))
        self.export_button.setEnabled(not busy and bool(self.results) and (self.search_done or bool(self.completed_indices)))
        self.cancel_button.setEnabled(busy)
        self.open_button.setEnabled(not busy and self.report_path is not None)

    def open_report(self):
        if self.report_path and not QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.report_path.resolve()))):
            QMessageBox.warning(self, "Nie można otworzyć raportu", f"Otwórz plik ręcznie:\n{self.report_path}")

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.cancel_search()
            event.ignore()
            self.status.setText("Trwa anulowanie. Zamknij okno po zakończeniu bieżącego żądania.")
        else:
            event.accept()


def main():
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-test", type=Path)
    arguments, _ = parser.parse_known_args()
    if arguments.self_test:
        from .self_test import run_self_test
        sys.exit(run_self_test(arguments.self_test))
    application = QApplication(sys.argv)
    application.setApplicationName("MovieCheck")
    application.setOrganizationName("MovieCheck")
    application.setApplicationVersion(__version__)
    configure_logging(Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)))
    window = MainWindow()
    window.show()
    sys.exit(application.exec())

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QVBoxLayout, QWidget,
)

from .cache import MovieCache
from .inputs import load_queries, suggested_report_path
from .models import MovieQuery, MovieResult
from .providers import validate_movie_url
from .report import translate_genres, write_report
from .service import MovieService


class SearchWorker(QThread):
    result_ready = Signal(int, object)
    progress = Signal(int, int, str)
    failed = Signal(str)

    def __init__(self, jobs, cache_path: Path, use_cache: bool, parent=None):
        super().__init__(parent)
        self.jobs = jobs
        self.cache_path = cache_path
        self.use_cache = use_cache
        self.partial = True
        self.error = ""

    def run(self):
        cache = None
        service = None
        try:
            cache = MovieCache(self.cache_path, self.use_cache)
            service = MovieService(cache, self.isInterruptionRequested)
            for position, (index, query, override) in enumerate(self.jobs):
                if self.isInterruptionRequested():
                    break
                self.progress.emit(position, len(self.jobs), query.title)
                result = service.lookup(query, override)
                if self.isInterruptionRequested():
                    break
                self.result_ready.emit(index, result)
                self.progress.emit(position + 1, len(self.jobs), query.title)
            self.partial = self.isInterruptionRequested()
        except Exception as error:
            self.error = f"{type(error).__name__}: {error}"
            self.failed.emit(self.error)
        finally:
            if service:
                service.close()
            if cache:
                cache.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MovieCheck — katalog filmów")
        self.resize(1180, 760)
        self.settings = QSettings("MovieCheck", "MovieCheck")
        self.source = None
        self.results = []
        self.worker = None
        self.report_path = None
        self.report_partial = False
        self.job_output = None
        self.completed_indices = set()

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
        self.use_cache = QCheckBox("Używaj lokalnej pamięci wyników (7 dni)")
        self.use_cache.setChecked(True)
        options.addWidget(self.recursive)
        options.addWidget(self.use_cache)
        options.addStretch()
        layout.addLayout(options)

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
        self.search_button = QPushButton("Wyszukaj wszystkie filmy")
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
        self.export_button = QPushButton("Zapisz raport")
        self.export_button.clicked.connect(self.export_report)
        for button in (self.search_button, self.cancel_button, self.correct_button, self.link_button, self.export_button, self.open_button):
            actions.addWidget(button)
        layout.addLayout(actions)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Plik", "Tytuł", "Rok", "Oceny", "Gatunki", "Stan"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 230)
        self.table.setColumnWidth(2, 60)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 170)
        self.table.itemSelectionChanged.connect(self.show_details)
        layout.addWidget(self.table, 1)
        self.details = QLabel("Wyniki niejednoznaczne można poprawić, wskazując link do właściwego filmu.")
        self.details.setWordWrap(True)
        # Treść z nazw plików i sieci zawsze jest zwykłym tekstem.
        from PySide6.QtCore import Qt
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.details)
        self.status = QLabel("Gotowe do wczytania listy filmów.")
        layout.addWidget(self.status)
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
        self.report_path = None
        self.table.setRowCount(len(queries))
        for index, result in enumerate(self.results):
            self.update_row(index, result)
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
        output = Path(self.output_path.text())
        if output.exists() and QMessageBox.question(self, "Zastąpić raport?", f"Plik już istnieje:\n{output}\n\nZastąpić go po wyszukiwaniu?") != QMessageBox.StandardButton.Yes:
            return
        self.job_output = output
        cache_directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
        self.worker = SearchWorker(jobs, cache_directory / "movies.sqlite3", self.use_cache.isChecked(), self)
        self.worker.result_ready.connect(self.receive_result)
        self.worker.progress.connect(self.update_progress)
        self.worker.failed.connect(lambda message: QMessageBox.warning(self, "Błąd wyszukiwania", message))
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
        self.set_busy(False)
        if worker.error:
            self.status.setText("Wyszukiwanie zakończone błędem. Możesz spróbować ponownie.")
        else:
            self.report_partial = worker.partial or len(self.completed_indices) < len(self.results)
            self.save_report(self.job_output, self.report_partial)
        worker.deleteLater()

    def save_report(self, output: Path, partial: bool):
        try:
            write_report(output, self.source, self.results, partial)
        except (OSError, ValueError) as error:
            self.status.setText("Nie udało się zapisać raportu. Wyniki pozostały w tabeli.")
            QMessageBox.warning(self, "Błąd zapisu raportu", str(error))
            return
        self.report_path = output
        self.open_button.setEnabled(True)
        found = sum(bool(result.entries) for result in self.results)
        prefix = "Zapisano raport częściowy" if partial else "Zapisano raport"
        self.status.setText(f"{prefix}: {output} · Z danymi: {found}/{len(self.results)}")

    def export_report(self):
        if not self.source:
            return
        output = Path(self.output_path.text())
        if output.exists() and QMessageBox.question(self, "Zastąpić raport?", f"Zastąpić plik:\n{output}?") != QMessageBox.StandardButton.Yes:
            return
        self.save_report(output, self.report_partial or len(self.completed_indices) < len(self.results))

    def update_row(self, index: int, result: MovieResult):
        movie = result.primary
        genres = next((entry.genres for entry in result.entries if entry.genres), [])
        ratings = " | ".join(f"{entry.source}: {entry.rating}/{entry.rating_scale}" if entry.rating else f"{entry.source}: brak" for entry in result.entries)
        values = [result.query.filename, movie.title if movie else result.query.title,
                  str((movie.year if movie else None) or result.query.year or ""), ratings,
                  translate_genres(genres), result.status if index in self.completed_indices else "Oczekuje"]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip("\n".join(result.notes) if column == 5 else value)
            self.table.setItem(index, column, item)

    def show_details(self):
        index = self.table.currentRow()
        if index < 0 or index >= len(self.results):
            return
        result = self.results[index]
        description = result.description_entry
        text = (f"{description.description}\nOpis: {description.source}" if description else "Brak opisu.")
        if result.notes:
            text += "\n" + "\n".join(result.notes)
        self.details.setText(text[:1800])

    def correct_query(self):
        index = self.table.currentRow()
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
        index = self.table.currentRow()
        if index < 0:
            QMessageBox.information(self, "Wybierz film", "Najpierw zaznacz wiersz na liście.")
            return
        result = self.results[index]
        url, accepted = QInputDialog.getText(self, "Wskaż właściwy film", "Pełny adres HTTPS filmu w Filmweb lub IMDb:", text=result.primary.url if result.primary else "")
        if not accepted or not url.strip():
            return
        try:
            from urllib.parse import urlsplit
            source = "Filmweb" if urlsplit(url.strip()).hostname in ("filmweb.pl", "www.filmweb.pl") else "IMDb"
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
        for control in (self.directory_button, self.text_button, self.recursive, self.use_cache):
            control.setEnabled(not busy)
        for control in (self.search_button, self.correct_button, self.link_button, self.output_button, self.export_button):
            control.setEnabled(not busy and bool(self.results))
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
    application = QApplication(sys.argv)
    application.setApplicationName("MovieCheck")
    application.setOrganizationName("MovieCheck")
    window = MainWindow()
    window.show()
    sys.exit(application.exec())

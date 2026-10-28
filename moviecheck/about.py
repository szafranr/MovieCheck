"""Informacje o wydaniu i rzeczywiste ścieżki używane przez aplikację."""

import sys
from datetime import date
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from . import __author__, __release_date__, __version__


def data_directory() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))


def application_paths() -> dict[str, Path]:
    directory = data_directory()
    paths = {"log": directory / "errors.log", "database": directory / "movies.sqlite3"}
    if sys.platform == "darwin":
        paths["crashes"] = Path.home() / "Library" / "Logs" / "DiagnosticReports"
    return paths


def application_information(paths=None) -> str:
    paths = application_paths() if paths is None else paths
    published = date.fromisoformat(__release_date__).strftime("%d.%m.%Y")
    lines = ["MovieCheck", "Wersja: " + __version__, "Data publikacji: " + published,
             "Autor: " + __author__, "Log aplikacji: " + str(paths["log"]),
             "Baza danych: " + str(paths["database"]), "Kopie logu: errors.log.1, errors.log.2"]
    if "crashes" in paths:
        lines.append("Systemowe raporty awarii macOS: " + str(paths["crashes"]))
    return "\n".join(lines)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("O programie — MovieCheck")
        self.resize(700, 360)
        self.paths = application_paths()
        self.information = application_information(self.paths)
        layout = QVBoxLayout(self)
        title = QLabel("MovieCheck")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        form = QFormLayout()
        for label, value in (("Wersja:", __version__), ("Data publikacji:", date.fromisoformat(__release_date__).strftime("%d.%m.%Y")), ("Autor:", __author__)):
            field = QLabel(value)
            field.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(label, field)
        for key, label in (("log", "Log aplikacji:"), ("database", "Baza danych:"), ("crashes", "Raporty awarii macOS:")):
            if key in self.paths:
                field = QLineEdit(str(self.paths[key]))
                field.setObjectName(key + "Path")
                field.setReadOnly(True)
                field.setCursorPosition(0)
                form.addRow(label, field)
        layout.addLayout(form)
        note = QLabel("Starsze wpisy logu: errors.log.1 i errors.log.2.\n"
                      "Nagłe zamknięcie procesu może wymagać systemowego raportu awarii; nie każdy crash trafia do errors.log.\n"
                      "Bez klucza API TMDB nie wykonuje zapytań do API; Filmweb i IMDb działają dalej.")
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        copy = QPushButton("Kopiuj informacje")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.information))
        buttons.addButton(copy, QDialogButtonBox.ButtonRole.ActionRole)
        self.copy_button = copy
        open_data = QPushButton("Otwórz folder logów i bazy")
        open_data.clicked.connect(lambda: self.open_directory(self.paths["log"].parent))
        buttons.addButton(open_data, QDialogButtonBox.ButtonRole.ActionRole)
        if "crashes" in self.paths:
            open_crashes = QPushButton("Otwórz raporty awarii")
            open_crashes.clicked.connect(lambda: self.open_directory(self.paths["crashes"]))
            buttons.addButton(open_crashes, QDialogButtonBox.ButtonRole.ActionRole)
        layout.addWidget(buttons)

    def open_directory(self, path):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "Nie można otworzyć folderu", "Otwórz folder ręcznie:\n" + str(path))

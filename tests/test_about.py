import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit
from moviecheck import __author__, __release_date__, __version__
from moviecheck.about import AboutDialog, application_paths
from moviecheck.app import MainWindow
from moviecheck.cache import MovieCache
from moviecheck.models import MovieData, MovieQuery
from moviecheck.service import MovieService


class AboutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_about_shows_metadata_paths_and_copies_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory, patch("moviecheck.about.QStandardPaths.writableLocation", return_value=directory):
            dialog = AboutDialog()
            try:
                labels = [label.text() for label in dialog.findChildren(QLabel)]
                self.assertIn("MovieCheck", labels)
                self.assertIn(__version__, labels)
                self.assertIn("Robert Szafrański", labels)
                self.assertIn(date.fromisoformat(__release_date__).strftime("%d.%m.%Y"), labels)
                for key, filename in (("log", "errors.log"), ("database", "movies.sqlite3")):
                    field = dialog.findChild(QLineEdit, key + "Path")
                    self.assertTrue(field.isReadOnly())
                    self.assertEqual(Path(field.text()), Path(directory) / filename)
                dialog.copy_button.click()
                copied = self.application.clipboard().text()
                self.assertIn(__author__, copied)
                self.assertIn(str(Path(directory) / "errors.log"), copied)
                self.assertIn(str(Path(directory) / "movies.sqlite3"), copied)
                with patch("moviecheck.about.QDesktopServices.openUrl", return_value=True) as open_url:
                    dialog.open_directory(Path(directory))
                self.assertEqual(Path(open_url.call_args.args[0].toLocalFile()), Path(directory))
            finally:
                dialog.close()

    def test_macos_system_crash_location_is_separate_from_application_log(self):
        with patch("moviecheck.about.sys.platform", "darwin"), patch("moviecheck.about.Path.home", return_value=Path("/Users/fixture")), patch("moviecheck.about.QStandardPaths.writableLocation", return_value="/fixture/data"):
            paths = application_paths()
        self.assertEqual(paths["crashes"], Path("/Users/fixture/Library/Logs/DiagnosticReports"))
        self.assertEqual(paths["log"], Path("/fixture/data/errors.log"))
        self.assertEqual(paths["database"], Path("/fixture/data/movies.sqlite3"))

    def test_about_button_opens_dialog_without_starting_search(self):
        window = MainWindow()
        try:
            with patch("moviecheck.app.AboutDialog") as dialog:
                window.about_button.click()
                dialog.assert_called_once_with(window)
                dialog.return_value.exec.assert_called_once()
            self.assertIsNone(window.worker)
        finally:
            window.close()

    def test_no_tmdb_key_keeps_filmweb_imdb_and_makes_no_api_requests(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"TMDB_READ_ACCESS_TOKEN": "", "TMDB_API_KEY": ""}):
            cache = MovieCache(Path(directory) / "cache.sqlite3")
            service = MovieService(cache)
            try:
                filmweb = MovieData("Film", "https://www.filmweb.pl/film/Film-2020-1", "Filmweb", description="Opis filmu.", rating="7.3")
                imdb = MovieData("Film", "https://www.imdb.com/title/tt1", "IMDb", rating="8.1")
                with patch.object(service.providers[0], "search", return_value=filmweb), patch.object(service.providers[1], "search", return_value=imdb), patch.object(service.vod, "lookup"), patch.object(service.providers[2].client, "get") as api:
                    result = service.lookup(MovieQuery("Film.mkv", "Film"))
                api.assert_not_called()
                self.assertEqual([entry.source for entry in result.entries], ["Filmweb", "IMDb"])
                self.assertEqual(result.status, "Znaleziono")
                self.assertIsNone(result.entry_for("TMDB"))
                self.assertTrue(any("klucz" in note for note in result.notes))
            finally:
                service.close()
                cache.close()

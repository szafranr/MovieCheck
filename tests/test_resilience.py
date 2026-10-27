import logging
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bs4 import BeautifulSoup
from PySide6.QtWidgets import QApplication

from moviecheck.app import MainWindow, SearchWorker
from moviecheck.diagnostics import configure_logging
from moviecheck.models import MovieData, MovieQuery, MovieResult


def successful_result(query):
    return MovieResult(query, [MovieData(query.title, "https://www.imdb.com/title/tt1", "IMDb", description="Opis dla " + query.title, rating="7.1")])


class BatchResilienceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def wait_for_window(self, window):
        deadline = time.monotonic() + 10
        while window.worker is not None and time.monotonic() < deadline:
            self.application.processEvents()
            time.sleep(0.01)
        if window.worker is not None:
            window.worker.requestInterruption()
            window.worker.wait(5000)
            self.application.processEvents()
            self.fail("Wyszukiwanie nie zakończyło się w wymaganym czasie.")

    def test_error_at_eighty_percent_continues_and_writes_complete_html(self):
        for exception in (OSError(22, "Invalid argument"), TypeError("Nieprawidłowe dane filmu")):
            with self.subTest(exception=type(exception).__name__), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                listing = root / "lista.txt"
                listing.write_text("\n".join(f"Movie{index:02d}.2020.mkv" for index in range(10)), encoding="utf-8")
                window = MainWindow()
                window.load_source(listing)

                def lookup(query, override):
                    if query.title == "Movie08":
                        raise exception
                    return successful_result(query)

                with patch("moviecheck.app.MovieCache"), patch("moviecheck.app.MovieService") as service, patch("moviecheck.app.QMessageBox.warning") as warning, self.assertLogs("moviecheck.app", level="ERROR"):
                    service.return_value.lookup.side_effect = lookup
                    window.start_all()
                    self.wait_for_window(window)
                    self.assertEqual(service.return_value.lookup.call_count, 10)
                    warning.assert_not_called()
                self.assertEqual(window.progress.value(), 10)
                self.assertFalse(window.report_partial)
                self.assertTrue(window.open_button.isEnabled())
                self.assertIn(type(exception).__name__, window.results[8].notes[0])
                self.assertEqual(window.results[9].status, "Znaleziono")
                html = (root / "lista.html").read_text(encoding="utf-8")
                articles = BeautifulSoup(html, "html.parser").select("article")
                self.assertEqual(len(articles), 10)
                self.assertIn(type(exception).__name__, articles[8].get_text())
                self.assertIn("Opis dla Movie09", articles[9].get_text())
                self.assertNotIn("Raport częściowy", html)
                window.close()
                window.deleteLater()
                self.application.processEvents()

    def test_fatal_error_saves_partial_report_before_showing_dialog(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            listing = root / "lista.txt"
            listing.write_text("Movie00.2020.mkv\nMovie01.2020.mkv", encoding="utf-8")
            window = MainWindow()
            window.load_source(listing)
            window.receive_result(0, successful_result(window.results[0].query))
            report = root / "lista.html"

            def show_warning(*arguments):
                self.assertTrue(report.exists())

            with patch("moviecheck.app.MovieCache", side_effect=OSError(22, "Invalid argument")), patch("moviecheck.app.QMessageBox.warning", side_effect=show_warning) as warning, self.assertLogs("moviecheck.app", level="ERROR"):
                window.start_all()
                self.wait_for_window(window)
                warning.assert_called_once()
            self.assertTrue(window.report_partial)
            html = report.read_text(encoding="utf-8")
            self.assertIn("Raport częściowy", html)
            self.assertIn("Opis dla Movie00", html)
            self.assertIn("Wyszukiwanie przerwane: OSError", html)
            self.assertTrue(window.open_button.isEnabled())
            window.close()
            window.deleteLater()
            self.application.processEvents()

    def test_cleanup_failure_does_not_skip_closing_other_resources(self):
        query = MovieQuery("Film.mkv", "Film")
        worker = SearchWorker([(0, query, "")], Path("unused.sqlite3"), True)
        received = []
        worker.result_ready.connect(lambda index, result: received.append(result))
        with patch("moviecheck.app.MovieCache") as cache, patch("moviecheck.app.MovieService") as service, self.assertLogs("moviecheck.app", level="ERROR"):
            service.return_value.lookup.return_value = successful_result(query)
            service.return_value.close.side_effect = OSError(22, "Invalid argument")
            worker.run()
            cache.return_value.close.assert_called_once()
        self.assertEqual(len(received), 1)
        self.assertTrue(worker.partial)
        self.assertIn("OSError", worker.error)


class DiagnosticsTests(unittest.TestCase):
    def test_traceback_is_logged_and_unwritable_log_does_not_crash(self):
        logger = logging.getLogger("moviecheck")
        old_handlers, old_level, old_propagate = logger.handlers[:], logger.level, logger.propagate
        logger.handlers = []
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                configure_logging(root)
                try:
                    raise OSError(22, "Invalid argument")
                except OSError:
                    logging.getLogger("moviecheck.app").exception("Błąd dla Film.mkv")
                for handler in logger.handlers:
                    handler.close()
                log = (root / "errors.log").read_text(encoding="utf-8")
                self.assertIn("Film.mkv", log)
                self.assertIn("Traceback", log)
                self.assertIn("OSError", log)
                logger.handlers = []
                with patch("moviecheck.diagnostics.RotatingFileHandler", side_effect=PermissionError("Brak uprawnień")):
                    configure_logging(root)
                self.assertIsInstance(logger.handlers[0], logging.NullHandler)
        finally:
            for handler in logger.handlers:
                handler.close()
            logger.handlers = old_handlers
            logger.setLevel(old_level)
            logger.propagate = old_propagate

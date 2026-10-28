import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from moviecheck.app import MainWindow
from moviecheck import __version__
from moviecheck.models import MovieData, VodAvailability, VodOffer


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.application.setApplicationName("MovieCheckTest")

    def test_window_searches_then_exports_report_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            listing = root / "lista.txt"
            listing.write_text("Test.Movie.2020.mkv\n", encoding="utf-8")
            window = MainWindow()
            self.assertIn(__version__, window.windowTitle())
            self.assertFalse(window.windowIcon().isNull())
            window.load_source(listing)
            self.assertEqual(window.table.rowCount(), 1)
            self.assertEqual(window.table.item(0, 1).text(), "Test Movie")
            self.assertTrue(window.search_button.isEnabled())

            def fake_search(provider, query):
                url = "https://www.filmweb.pl/film/Test-2020-1" if provider.source == "Filmweb" else "https://www.imdb.com/title/tt1"
                return MovieData(query.title, url, provider.source, year=query.year,
                                 description="Opis testowy.", genres=["Drama"], rating="7" if provider.source == "Filmweb" else "8.1")

            vod = VodAvailability([VodOffer("Netflix", "https://www.netflix.com/title/1")], "2026-10-27 12:00")
            def show_completion(parent, title, message):
                self.assertFalse((root / "lista.html").exists())
                self.assertIn("Wygeneruj raport", message)
                self.assertEqual(title, "Wyszukiwanie zakończone")

            with patch("moviecheck.providers.WebProvider.search", autospec=True, side_effect=fake_search), patch("moviecheck.imdb.IMDbProvider.search", autospec=True, side_effect=fake_search), patch("moviecheck.vod.FilmwebVod.lookup", return_value=vod), patch("moviecheck.app.QMessageBox.warning") as warning, patch("moviecheck.app.QMessageBox.information", side_effect=show_completion) as information:
                window.start_all()
                self.assertFalse(window.search_button.isEnabled())
                deadline = time.monotonic() + 15
                while window.worker is not None and time.monotonic() < deadline:
                    self.application.processEvents()
                    time.sleep(0.01)
                if window.worker is not None:
                    window.worker.requestInterruption()
                    window.worker.wait(5000)
                    self.application.processEvents()
                    self.fail("Wątek wyszukiwania nie zakończył się w wymaganym czasie.")
                warning.assert_not_called()
                information.assert_called_once()
            self.assertFalse((root / "lista.html").exists())
            window.export_report()
            self.assertTrue((root / "lista.html").exists())
            self.assertEqual(window.table.item(0, 3).text(), "7/10")
            self.assertEqual(window.table.item(0, 4).text(), "8.1/10")
            self.assertEqual(window.table.item(0, 6).text(), "Netflix")
            self.assertEqual(window.table.item(0, 8).text(), "Znaleziono")
            self.assertTrue(window.open_button.isEnabled())
            self.assertTrue(window.search_button.isEnabled())
            window.close()
            window.deleteLater()
            self.application.processEvents()

    def test_failed_report_save_does_not_show_completion_message(self):
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            listing = root / "lista.txt"
            listing.write_text("Film.2020.mkv", encoding="utf-8")
            window = MainWindow()
            window.load_source(listing)
            window.worker = Mock(error="", partial=False)
            window.job_output = root / "lista.html"
            window.completed_indices = {0}
            with patch("moviecheck.app.write_report", side_effect=OSError("Brak uprawnień")), patch("moviecheck.app.QMessageBox.warning") as warning, patch("moviecheck.app.QMessageBox.information") as information:
                window.search_done = True
                window.worker = None
                window.export_report()
                warning.assert_called_once()
                information.assert_not_called()
            window.close()
            window.deleteLater()
            self.application.processEvents()

    def test_partial_search_does_not_generate_report(self):
        from unittest.mock import Mock

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            listing = root / "lista.txt"
            listing.write_text("Film.2020.mkv", encoding="utf-8")
            window = MainWindow()
            window.load_source(listing)
            window.worker = Mock(error="", partial=True)
            window.job_output = root / "lista.html"
            with patch("moviecheck.app.QMessageBox.information") as information:
                window.search_finished()
                self.assertFalse(window.job_output.exists())
                self.assertTrue(window.export_button.isEnabled())
                self.assertEqual(information.call_args.args[1], "Wyszukiwanie zakończone częściowo")
            window.close()
            window.deleteLater()
            self.application.processEvents()


if __name__ == "__main__":
    unittest.main()

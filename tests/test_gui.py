import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from moviecheck.app import MainWindow
from moviecheck.models import MovieData


class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])
        cls.application.setApplicationName("MovieCheckTest")

    def test_window_loads_searches_and_writes_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            listing = root / "lista.txt"
            listing.write_text("Test.Movie.2020.mkv\n", encoding="utf-8")
            window = MainWindow()
            window.load_source(listing)
            self.assertEqual(window.table.rowCount(), 1)
            self.assertEqual(window.table.item(0, 1).text(), "Test Movie")
            self.assertTrue(window.search_button.isEnabled())

            def fake_search(provider, query):
                return MovieData(query.title, "https://www.filmweb.pl/film/Test-2020-1", provider.source, year=query.year,
                                 description="Opis testowy.", genres=["Drama"], rating="7")

            with patch("moviecheck.providers.WebProvider.search", autospec=True, side_effect=fake_search), patch("moviecheck.app.QMessageBox.warning") as warning:
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
            self.assertTrue((root / "lista.html").exists())
            self.assertEqual(window.table.item(0, 5).text(), "Znaleziono")
            self.assertTrue(window.open_button.isEnabled())
            self.assertTrue(window.search_button.isEnabled())
            window.close()
            window.deleteLater()
            self.application.processEvents()


if __name__ == "__main__":
    unittest.main()

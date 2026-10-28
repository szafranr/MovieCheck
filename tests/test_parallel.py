import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from moviecheck.app import MainWindow, SearchWorker
from moviecheck.cache import MovieCache
from moviecheck.imdb import IMDbRatings
from moviecheck.models import MovieData, MovieQuery, MovieResult
from moviecheck.performance import BatchState
from moviecheck.providers import ProviderError


def result_for(query, score="8", source="IMDb"):
    url = {"IMDb": "https://www.imdb.com/title/tt1", "Filmweb": "https://www.filmweb.pl/film/Film-2020-1", "TMDB": "https://www.themoviedb.org/movie/1"}[source]
    return MovieResult(query, [MovieData(query.title, url, source, year=2020, rating=score, description="Opis " + query.title)])


class ParallelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_titles_actually_overlap_and_each_thread_owns_its_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            barrier = threading.Barrier(4)
            threads = set()
            class Service:
                def __init__(self, cache, *args):
                    self.cache = cache
                def lookup(self, query, override):
                    threads.add(threading.get_ident())
                    barrier.wait(5)
                    self.cache.put(query.filename, {"title": query.title})
                    return result_for(query)
                def close(self):
                    pass
            jobs = [(index, MovieQuery(f"{index}.mkv", str(index)), "") for index in range(4)]
            worker = SearchWorker(jobs, Path(directory) / "cache.sqlite3", True, workers=4)
            received, progress = [], []
            worker.result_ready.connect(lambda index, result: received.append((index, result)), Qt.ConnectionType.DirectConnection)
            worker.progress.connect(lambda done, total, text: progress.append(done), Qt.ConnectionType.DirectConnection)
            with patch("moviecheck.app.MovieService", Service):
                worker.run()
            self.assertEqual(worker.error, "")
            self.assertFalse(worker.partial)
            self.assertEqual(len(threads), 4)
            self.assertNotIn(threading.get_ident(), threads)
            self.assertEqual({index for index, result in received}, set(range(4)))
            self.assertEqual(progress, [1, 2, 3, 4])
            cache = MovieCache(Path(directory) / "cache.sqlite3")
            try:
                self.assertEqual([cache.get(f"{index}.mkv")["title"] for index in range(4)], [str(index) for index in range(4)])
            finally:
                cache.close()

    def test_cancellation_stops_scheduling_and_marks_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            started = []
            class Service:
                def __init__(self, *args):
                    pass
                def lookup(self, query, override):
                    started.append(query.title)
                    time.sleep(0.02)
                    return result_for(query)
                def close(self):
                    pass
            worker = SearchWorker([(index, MovieQuery(str(index), str(index)), "") for index in range(30)], Path(directory) / "cache.sqlite3", True, workers=2)
            received = []
            def receive(index, result):
                received.append(index)
                worker.requestInterruption()
            worker.result_ready.connect(receive, Qt.ConnectionType.DirectConnection)
            with patch("moviecheck.app.MovieService", Service):
                worker.start()
                self.assertTrue(worker.wait(10000))
            self.assertEqual(len(received), 1)
            self.assertLessEqual(len(started), 2)
            self.assertTrue(worker.partial)
            self.assertEqual(worker.error, "")

    def test_imdb_index_is_prepared_once_even_without_result_cache(self):
        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "cache.sqlite3"
                state = BatchState()
                initialize = threading.Lock()
                calls = []
                def download(ratings):
                    calls.append(1)
                    if failed:
                        raise ProviderError("Dataset unavailable")
                    connection = ratings.cache.connection
                    connection.execute("CREATE TABLE imdb_ratings (id TEXT PRIMARY KEY, rating TEXT)")
                    connection.execute("INSERT INTO imdb_ratings VALUES ('tt1', '8.2')")
                    connection.execute("INSERT OR REPLACE INTO imdb_metadata VALUES ('fetched', ?)", (time.time(),))
                    connection.commit()
                def lookup():
                    with initialize:
                        cache = MovieCache(path, enabled=False)
                    cache.batch_state = state
                    try:
                        ratings = IMDbRatings(cache)
                        try:
                            return ratings.get("tt1")
                        except ProviderError:
                            return "error"
                    finally:
                        cache.close()
                with patch.object(IMDbRatings, "download", download), ThreadPoolExecutor(max_workers=4) as pool:
                    results = list(pool.map(lambda _: lookup(), range(8)))
                self.assertEqual(results, ["error" if failed else "8.2"] * 8)
                self.assertEqual(len(calls), 1)

    def make_window(self, root):
        listing = root / "lista.txt"
        listing.write_text("Alpha.2020.mkv\nBeta.2020.mkv\nGamma.2020.mkv", encoding="utf-8")
        window = MainWindow()
        window.load_source(listing)
        self.addCleanup(window.deleteLater)
        self.addCleanup(window.close)
        return window

    def test_all_ratings_sort_numerically_and_html_preserves_visible_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            window = self.make_window(root)
            for index, score in enumerate(("8.5", "10", "")):
                query = window.results[index].query
                entries = [result_for(query, score, source).primary for source in ("Filmweb", "IMDb", "TMDB")]
                window.receive_result(index, MovieResult(query, entries))
            for column in (3, 4, 5):
                window.table.sortItems(column, Qt.SortOrder.DescendingOrder)
                self.assertEqual([result.query.title for result in window.ordered_results()], ["Beta", "Alpha", "Gamma"])
            window.export_report()
            html = (root / "lista.html").read_text(encoding="utf-8")
            self.assertLess(html.index("Beta.2020"), html.index("Alpha.2020"))
            self.assertLess(html.index("Alpha.2020"), html.index("Gamma.2020"))
            window.table.sortItems(1, Qt.SortOrder.AscendingOrder)
            self.assertEqual([result.query.title for result in window.ordered_results()], ["Alpha", "Beta", "Gamma"])

    def test_link_correction_and_late_result_keep_identity_after_sort(self):
        with tempfile.TemporaryDirectory() as directory:
            window = self.make_window(Path(directory))
            for index in (2, 0, 1):
                window.receive_result(index, result_for(window.results[index].query, str(index + 5)))
            window.table.sortItems(1, Qt.SortOrder.DescendingOrder)
            self.assertEqual(window.result_index(0), 2)
            item = window.table.item(0, 1)
            with patch("moviecheck.app.QDesktopServices.openUrl") as open_url:
                window.open_title_link(item)
                self.assertEqual(open_url.call_args.args[0].toString(), "https://www.imdb.com/title/tt1")
            window.table.selectRow(0)
            with patch("moviecheck.app.QInputDialog.getText", side_effect=[("Changed Gamma", True), ("2021", True)]):
                window.correct_query()
            self.assertEqual(window.results[2].query.title, "Changed Gamma")
            self.assertEqual(window.results[0].query.title, "Alpha")
            window.receive_result(1, result_for(window.results[1].query, "9.9"))
            row = next(row for row in range(3) if window.result_index(row) == 1)
            self.assertEqual(window.table.item(row, 1).text(), "Beta")
            self.assertEqual(window.table.item(row, 4).text(), "9.9/10")

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moviecheck.cache import MovieCache
from moviecheck.imdb import IMDbProvider, IMDbRatings
from moviecheck.models import MovieData, MovieQuery
from moviecheck.providers import ProviderError


class IMDbTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.cache = MovieCache(self.root / "cache.sqlite3")
        self.provider = IMDbProvider(self.cache)

    def tearDown(self):
        self.provider.close()
        self.cache.close()
        self.directory.cleanup()

    def import_fixture(self, content="tconst\taverageRating\tnumVotes\ntt38984885\t4.1\t123\ntt1375666\t8.8\t1000\n"):
        path = self.root / "ratings.tsv.gz"
        with gzip.open(path, "wt", encoding="utf-8") as output:
            output.write(content)
        self.provider.ratings.import_ratings(path)
        return path

    def test_official_ratings_are_indexed_and_missing_rating_is_not_zero(self):
        self.import_fixture()
        with patch.object(self.provider.ratings, "download") as download:
            self.assertEqual(self.provider.ratings.get("tt38984885"), "4.1")
            self.assertEqual(self.provider.ratings.get("tt999999999"), "")
            download.assert_not_called()

    def test_blocked_page_uses_independent_dataset_and_preserves_identity(self):
        self.import_fixture()
        url = "https://www.imdb.com/title/tt38984885"
        self.provider.suggestions[url] = MovieData("Betty's Revenge", url, "IMDb", 2026)
        with patch.object(self.provider, "fetch", side_effect=ProviderError("HTTP 202")) as fetch:
            movie = self.provider.get_movie(url)
            self.assertEqual((movie.title, movie.year, movie.rating), ("Betty's Revenge", 2026, "4.1"))
            self.assertIn("oficjalny", movie.rating_source)
            self.provider.get_movie(url)
            fetch.assert_called_once()

    def test_suggestions_reject_wrong_year_and_episode(self):
        data = {"d": [{"id": "tt1", "l": "Betty's Revenge", "y": 2025, "qid": "movie"}, {"id": "tt2", "l": "Betty's Revenge", "y": 2026, "qid": "tvEpisode"}, {"id": "tt38984885", "l": "Betty's Revenge", "y": 2026, "qid": "movie"}]}
        movie = MovieData("Betty's Revenge", "https://www.imdb.com/title/tt38984885", "IMDb", 2026)
        with patch.object(self.provider, "fetch", return_value=json.dumps(data)), patch.object(self.provider, "get_movie", return_value=movie) as get:
            self.assertIs(self.provider.search(MovieQuery("Bettys.mkv", "Bettys Revenge", 2026)), movie)
            get.assert_called_once_with(movie.url)

    def test_manual_id_without_title_does_not_override_later_identification(self):
        self.import_fixture()
        url = "https://www.imdb.com/title/tt1375666"
        with patch.object(self.provider, "fetch", side_effect=ProviderError("HTTP 202")):
            self.assertEqual(self.provider.get_movie(url).title, "Film IMDb tt1375666")
        self.assertIsNone(self.cache.get(url))
        self.provider.suggestions[url] = MovieData("Inception", url, "IMDb", 2010)
        movie = self.provider.get_movie(url)
        self.assertEqual((movie.title, movie.year, movie.rating), ("Inception", 2010, "8.8"))

    def test_suggestions_retry_missing_apostrophe(self):
        hit = {"d": [{"id": "tt38984885", "l": "Betty's Revenge", "y": 2026, "qid": "movie"}]}
        with patch.object(self.provider, "fetch", side_effect=[json.dumps({"d": []}), json.dumps(hit)]) as fetch, patch.object(self.provider, "get_movie", return_value=MovieData("Betty's Revenge", "https://www.imdb.com/title/tt38984885", "IMDb", 2026)):
            self.assertIsNotNone(self.provider.search(MovieQuery("Bettys.mkv", "Bettys Revenge", 2026)))
            self.assertIn("betty%27s%20revenge.json", fetch.call_args_list[1].args[0])

    def test_confirmed_year_takes_priority_over_unknown_year(self):
        data = {"d": [{"id": "tt1", "l": "Inception", "qid": "movie"}, {"id": "tt1375666", "l": "Inception", "y": 2010, "qid": "movie"}]}
        with patch.object(self.provider, "fetch", return_value=json.dumps(data)), patch.object(self.provider, "get_movie", return_value=MovieData("Inception", "https://www.imdb.com/title/tt1375666", "IMDb", 2010)) as get:
            self.provider.search(MovieQuery("Inception.mkv", "Inception", 2010))
            get.assert_called_once_with("https://www.imdb.com/title/tt1375666")

    def test_short_display_title_requires_matching_year_and_exact_main_title(self):
        data = {"d": [{"id": "tt11564570", "l": "Glass Onion", "y": 2022, "qid": "movie"}]}
        with patch.object(self.provider, "fetch", return_value=json.dumps(data)), patch.object(self.provider, "get_movie", return_value=MovieData("Glass Onion", "https://www.imdb.com/title/tt11564570", "IMDb", 2022)) as get:
            self.assertIsNotNone(self.provider.search(MovieQuery("Film.mkv", "Glass Onion: A Knives Out Mystery", 2022)))
            get.assert_called_once_with("https://www.imdb.com/title/tt11564570")
        for year in (None, 2021):
            with self.subTest(year=year), patch.object(self.provider, "fetch", return_value=json.dumps(data)), patch.object(self.provider, "get_movie") as get:
                self.assertIsNone(self.provider.search(MovieQuery("Film.mkv", "Glass Onion: A Knives Out Mystery", year)))
                get.assert_not_called()

    def test_dataset_rating_cache_does_not_extend_dataset_freshness(self):
        self.import_fixture()
        url = "https://www.imdb.com/title/tt1375666"
        self.cache.put(url, {"title": "Inception", "url": url, "source": "IMDb", "rating": "8.8", "rating_source": "IMDb — oficjalny zbiór ocen"})
        self.cache.connection.execute("UPDATE imdb_metadata SET value = 0")
        self.cache.connection.commit()
        with patch.object(self.provider.ratings, "download", side_effect=ProviderError("Brak sieci")) as download:
            movie = self.provider.get_movie(url)
            self.assertEqual(movie.rating, "")
            self.assertIn("Brak sieci", movie.provider_notes[0])
            download.assert_called_once()

    def test_disabled_result_cache_refreshes_dataset_once_per_batch(self):
        self.import_fixture()
        self.cache.enabled = False
        with patch.object(self.provider.ratings, "download") as download:
            self.provider.ratings.get("tt1375666")
            self.provider.ratings.get("tt38984885")
            download.assert_called_once()

    def test_ambiguous_suggestions_are_not_accepted(self):
        data = {"d": [{"id": "tt1", "l": "Film", "qid": "movie"}, {"id": "tt2", "l": "Film", "qid": "movie"}]}
        with patch.object(self.provider, "fetch", return_value=json.dumps(data)), self.assertRaisesRegex(ProviderError, "Niejednoznaczne"):
            self.provider.search(MovieQuery("Film.mkv", "Film"))

    def test_failed_download_is_not_repeated_for_every_movie(self):
        with patch.object(self.provider.ratings, "download", side_effect=ProviderError("Sieć niedostępna")) as download:
            for movie_id in ("tt1", "tt2"):
                with self.assertRaises(ProviderError):
                    self.provider.ratings.get(movie_id)
            download.assert_called_once()

    def test_cancelled_import_does_not_replace_previous_ratings(self):
        path = self.import_fixture()
        ratings = IMDbRatings(self.cache, cancelled=lambda: True)
        with self.assertRaises(ProviderError):
            ratings.import_ratings(path)
        self.assertEqual(self.provider.ratings.get("tt1375666"), "8.8")

    def test_invalid_header_does_not_replace_previous_ratings(self):
        self.import_fixture()
        path = self.root / "bad.tsv.gz"
        with gzip.open(path, "wt", encoding="utf-8") as output:
            output.write("wrong\tcolumns\n1\t2\n")
        with self.assertRaises(ProviderError):
            self.provider.ratings.import_ratings(path)
        self.assertEqual(self.provider.ratings.get("tt1375666"), "8.8")

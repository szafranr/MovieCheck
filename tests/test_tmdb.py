import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from bs4 import BeautifulSoup
from moviecheck.cache import MovieCache
from moviecheck.models import MovieData, MovieQuery, MovieResult
from moviecheck.providers import ProviderError, validate_movie_url
from moviecheck.report import write_report
from moviecheck.tmdb import TMDBProvider


class TMDBTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache = MovieCache(Path(self.directory.name) / "cache.sqlite3")
        self.addCleanup(self.cache.close)
        self.provider = TMDBProvider(self.cache, "private-token-fixture")
        self.addCleanup(self.provider.close)

    def transport(self, handler):
        self.provider.client.close()
        self.provider.client = httpx.Client(transport=httpx.MockTransport(handler))

    def payload(self, **changes):
        return {"id": 42, "title": "Film", "original_title": "Movie", "release_date": "2020-01-01",
                "vote_average": 8.25, "vote_count": 120, "poster_path": "/cover.jpg", "overview": "Polski opis.", **changes}

    def test_bearer_search_rating_poster_and_cache(self):
        requests = []
        def respond(request):
            requests.append(request)
            self.assertEqual(request.headers["Authorization"], "Bearer private-token-fixture")
            self.assertEqual(request.url.params["language"], "pl-PL")
            if request.url.path.endswith("search/movie"):
                self.assertEqual(request.url.params["year"], "2020")
                return httpx.Response(200, json={"results": [self.payload()]})
            return httpx.Response(200, json=self.payload(genres=[{"id": 18, "name": "Dramat"}]))
        self.transport(respond)
        query = MovieQuery("Movie.2020.mkv", "Movie", 2020)
        movie = self.provider.search(query)
        self.assertEqual((movie.rating, movie.rating_source), ("8.25", "TMDB — vote_average"))
        self.assertEqual(movie.poster_url, "https://image.tmdb.org/t/p/w500/cover.jpg")
        self.assertEqual(movie.genres, ["Dramat"])
        self.provider.search(query)
        self.assertEqual(len(requests), 2)
        keys = [row[0] for row in self.cache.connection.execute("SELECT url FROM movies")]
        self.assertFalse(any("private-token" in key for key in keys))

    def test_no_votes_is_missing_score_and_unsafe_poster_is_rejected(self):
        movie = self.provider.movie(self.payload(vote_count=0, poster_path="https://evil.example/a.jpg"))
        self.assertEqual(movie.rating, "")
        self.assertEqual(movie.poster_url, "")
        self.assertEqual(self.provider.movie(self.payload(vote_average=0)).rating, "0")
        self.assertEqual(self.provider.movie(self.payload(vote_average=float("nan"))).rating, "")

    def test_ambiguity_and_wrong_year_are_not_accepted(self):
        self.transport(lambda request: httpx.Response(200, json={"results": [self.payload(), self.payload(id=43)]}))
        with self.assertRaisesRegex(ProviderError, "Niejednoznaczne"):
            self.provider.search(MovieQuery("Movie.mkv", "Movie", 2020))
        self.assertIsNone(self.provider.search(MovieQuery("Movie.mkv", "Movie", 2019)))

    def test_imdb_id_uses_find_and_english_description_fallback(self):
        paths = []
        def respond(request):
            paths.append(request.url.path)
            if "/find/" in request.url.path:
                self.assertEqual(request.url.params["external_source"], "imdb_id")
                return httpx.Response(200, json={"movie_results": [self.payload()]})
            return httpx.Response(200, json=self.payload(overview="Plot." if request.url.params["language"] == "en-US" else ""))
        self.transport(respond)
        self.provider.imdb_id = "tt123"
        result = self.provider.search(MovieQuery("Movie.mkv", "Movie", 2020))
        self.assertEqual(result.description, "Plot.")
        self.assertEqual(paths, ["/3/find/tt123", "/3/movie/42", "/3/movie/42"])

    def test_api_key_is_not_exposed_in_errors_or_cache(self):
        self.provider.credential = "a" * 32
        def respond(request):
            self.assertEqual(request.url.params["api_key"], "a" * 32)
            return httpx.Response(401)
        self.transport(respond)
        with self.assertRaises(ProviderError) as caught:
            self.provider.request("/search/movie", query="Movie")
        self.assertNotIn("a" * 32, str(caught.exception))
        self.assertIn("token", str(caught.exception))

    def test_missing_credentials_makes_no_requests(self):
        self.provider.credential = ""
        with patch.object(self.provider.client, "get") as get, self.assertRaisesRegex(ProviderError, "klucz"):
            self.provider.request("/search/movie")
        get.assert_not_called()

    def test_tmdb_links_and_description_precedence(self):
        self.assertEqual(validate_movie_url("https://themoviedb.org/movie/42-film?lang=pl", "TMDB"), "https://www.themoviedb.org/movie/42-film")
        for url in ("https://themoviedb.org.evil/movie/42", "http://themoviedb.org/movie/42", "https://themoviedb.org/tv/42"):
            with self.assertRaises(ProviderError):
                validate_movie_url(url, "TMDB")
        filmweb = MovieData("Film", "https://www.filmweb.pl/film/Film-2020-1", "Filmweb", poster_url="https://example.org/fw.jpg")
        imdb = MovieData("Movie", "https://www.imdb.com/title/tt1", "IMDb", description="IMDb opis.")
        tmdb = self.provider.movie(self.payload())
        result = MovieResult(MovieQuery("Movie.mkv", "Movie"), [filmweb, imdb, tmdb])
        self.assertIs(result.primary, imdb)
        self.assertIs(result.poster_entry, tmdb)
        filmweb.description = "Filmweb opis."
        self.assertIs(result.primary, filmweb)
        path = Path(self.directory.name) / "report.html"
        write_report(path, Path("lista.txt"), [result])
        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        self.assertEqual(soup.select_one(".poster-link img")["src"], tmdb.poster_url)
        self.assertIn("TMDB: 8.25 / 10", soup.get_text())

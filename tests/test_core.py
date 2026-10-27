import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from moviecheck.cache import MovieCache
from moviecheck.inputs import extract_listing_names, load_queries, parse_filename, suggested_report_path
from moviecheck.models import MovieData, MovieQuery, MovieResult
from moviecheck.providers import ProviderError, WebProvider, match_score, normalized_title, parse_movie_page, search_title_variants, validate_movie_url
from moviecheck.report import write_report
from moviecheck.service import MovieService


class InputTests(unittest.TestCase):
    def test_release_tags_and_year(self):
        query = parse_filename("Inception.2010.1080p.BluRay.x264-GROUP.mkv")
        self.assertEqual((query.title, query.year), ("Inception", 2010))

    def test_number_is_part_of_title(self):
        self.assertEqual(parse_filename("1917.2019.1080p.mkv").title, "1917")
        query = parse_filename("2001.A.Space.Odyssey.1968.mkv")
        self.assertEqual((query.title, query.year), ("2001 A Space Odyssey", 1968))
        self.assertIsNone(parse_filename("1917.mkv").year)

    def test_windows_path_and_polish_name(self):
        query = parse_filename(r"D:\Filmy\Życie.jest.piękne.(1997).mp4")
        self.assertEqual((query.title, query.year), ("Życie jest piękne", 1997))

    def test_listings(self):
        content = """total 10
-rw-r--r-- 1 user staff 1234 Oct 27 12:00 A Movie (2020).mkv
-a----  27.10.2026  12:00  1234 Inception.2010.mp4
Another Film.2022.avi
notes.txt
"""
        self.assertEqual(extract_listing_names(content), ["A Movie (2020).mkv", "Inception.2010.mp4", "Another Film.2022.avi"])

    def test_encoding_filter_and_recursion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = root / "lista.txt"
            text.write_text("Życie.1997.mkv\nInception.2010.mp4\n", encoding="utf-16")
            self.assertEqual(len(load_queries(text)), 2)
            (root / "Movie.2020.mkv").touch()
            (root / "sub").mkdir()
            (root / "sub" / "Movie.2021.mp4").touch()
            self.assertEqual(len(load_queries(root)), 1)
            self.assertEqual(len(load_queries(root, True)), 2)
            self.assertEqual(suggested_report_path(root), root.parent / (root.name + ".html"))
            self.assertEqual(suggested_report_path(text), root / "lista.html")

    def test_empty_listing_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            text = Path(directory) / "empty.txt"
            text.write_text("notes.txt\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Nie znaleziono"):
                load_queries(text)


class ProviderTests(unittest.TestCase):
    def test_apostrophe_spellings_match_the_filename(self):
        query = parse_filename("Bettys Revenge.2026.1080p.AMZN.WEB-DL.DD2.0.H.264-BobDobbs.mkv")
        self.assertEqual((query.title, query.year), ("Bettys Revenge", 2026))
        for title in ("Bettys Revenge", "Betty's Revenge", "Betty’s Revenge", "BETTYʼS REVENGE", "Betty＇s Revenge", "Betty`s Revenge"):
            with self.subTest(title=title):
                movie = MovieData(title, "https://www.imdb.com/title/tt38984885", "IMDb", 2026)
                self.assertEqual(match_score(query, movie), 1.0)
        self.assertEqual(normalized_title("D’Artagnan"), normalized_title("DArtagnan"))
        self.assertEqual(normalized_title("Łódź — A-B"), "lodz a b")

    def test_apostrophe_matching_does_not_ignore_year_or_ambiguity(self):
        query = MovieQuery("Bettys.mkv", "Bettys Revenge", 2026)
        wrong_year = MovieData("Betty's Revenge", "https://www.imdb.com/title/tt1", "IMDb", 2025)
        self.assertEqual(match_score(query, wrong_year), 0.0)
        provider = WebProvider("IMDb", Mock())
        try:
            with patch.object(provider, "fetch", return_value='<a href="/title/tt1/">One</a><a href="/title/tt2/">Two</a>'), patch.object(provider, "get_movie", side_effect=[
                MovieData("Betty's Revenge", "https://www.imdb.com/title/tt1", "IMDb", 2026),
                MovieData("Bettys Revenge", "https://www.imdb.com/title/tt2", "IMDb", 2026),
            ]):
                with self.assertRaisesRegex(ProviderError, "Niejednoznaczne"):
                    provider.search(query)
        finally:
            provider.close()

    def test_search_variants_are_bounded_and_support_missing_apostrophe(self):
        self.assertEqual(search_title_variants("Bettys Revenge"), ["Bettys Revenge", "Betty's Revenge"])
        self.assertEqual(search_title_variants("Betty’s Revenge"), ["Betty’s Revenge", "Betty's Revenge", "Bettys Revenge"])
        self.assertEqual(search_title_variants("Inception"), ["Inception"])
        self.assertLessEqual(len(search_title_variants("James Jones Dogs Cats Birds")), 4)

    def test_imdb_search_retries_with_possessive_apostrophe(self):
        provider = WebProvider("IMDb", Mock())
        movie = MovieData("Betty's Revenge", "https://www.imdb.com/title/tt38984885", "IMDb", 2026, description="Opis testowy.")
        try:
            with patch.object(provider, "fetch", side_effect=["<html></html>", '<a href="/title/tt38984885/">Film</a>']) as fetch, patch.object(provider, "get_movie", return_value=movie):
                result = provider.search(MovieQuery("Bettys.mkv", "Bettys Revenge", 2026))
                self.assertIs(result, movie)
                self.assertIn("q=Bettys%20Revenge%202026", fetch.call_args_list[0].args[0])
                self.assertIn("q=Betty%27s%20Revenge%202026", fetch.call_args_list[1].args[0])
        finally:
            provider.close()

    def test_filmweb_search_retries_with_possessive_apostrophe(self):
        cache = Mock()
        cache.get.return_value = None
        provider = WebProvider("Filmweb", cache)
        movie = MovieData("Betty's Revenge", "https://www.filmweb.pl/film/Betty-2026-1", "Filmweb", 2026, description="Opis testowy.")
        responses = [json.dumps({"searchHits": []}), json.dumps({"searchHits": [{"id": 1, "type": "film"}]}), json.dumps({"title": {"title": "Betty"}, "year": 2026})]
        try:
            with patch.object(provider, "fetch", side_effect=responses) as fetch, patch.object(provider, "get_movie", return_value=movie):
                self.assertIs(provider.search(MovieQuery("Bettys.mkv", "Bettys Revenge", 2026)), movie)
                self.assertIn("query=Betty%27s%20Revenge", fetch.call_args_list[1].args[0])
        finally:
            provider.close()

    def test_successful_first_search_does_not_request_other_variants(self):
        provider = WebProvider("IMDb", Mock())
        movie = MovieData("Betty's Revenge", "https://www.imdb.com/title/tt38984885", "IMDb", 2026)
        try:
            with patch.object(provider, "fetch", return_value='<a href="/title/tt38984885/">Film</a>') as fetch, patch.object(provider, "get_movie", return_value=movie):
                self.assertIs(provider.search(MovieQuery("Bettys.mkv", "Bettys Revenge", 2026)), movie)
                fetch.assert_called_once()
        finally:
            provider.close()

    def test_empty_http_202_is_not_retried_as_another_spelling(self):
        import httpx

        provider = WebProvider("IMDb", Mock())
        provider.last_request = -100
        try:
            response = httpx.Response(202, text="", request=httpx.Request("GET", "https://www.imdb.com/find/"))
            with patch.object(provider.client, "get", return_value=response) as get:
                with self.assertRaisesRegex(ProviderError, "HTTP 202"):
                    provider.search(MovieQuery("Bettys.mkv", "Bettys Revenge", 2026))
                get.assert_called_once()
        finally:
            provider.close()

    def test_filmweb_microdata_without_json_ld(self):
        html = '''<h1 itemprop="name">Incepcja</h1>
        <h2 class="filmCoverSection__originalTitle">Inception <span>2010</span></h2>
        <div class="filmCoverSection__year">2010</div>
        <div itemprop="aggregateRating"><span itemprop="ratingValue">8,2</span><span itemprop="bestRating">10</span></div>
        <span itemprop="description">Opis testowy.</span><span itemprop="genre">Sci-Fi</span>'''
        movie = parse_movie_page(html, "https://www.filmweb.pl/film/Incepcja-2010-500891", "Filmweb")
        self.assertEqual((movie.title, movie.original_title, movie.year, movie.rating), ("Incepcja", "Inception", 2010, "8,2"))
        self.assertEqual(movie.genres, ["Sci-Fi"])
        self.assertEqual(movie.description, "Opis testowy.")

    def test_json_ld_graph(self):
        data = {"@graph": [{"@type": "WebPage"}, {"@type": "Movie", "name": "Incepcja", "alternateName": "Inception",
                "description": "Krótki opis.", "genre": ["Sci-Fi", "Thriller"], "datePublished": "2010-07-08",
                "aggregateRating": {"ratingValue": 8.2, "bestRating": 10}}]}
        html = '<script type="application/ld+json">' + json.dumps(data) + "</script>"
        movie = parse_movie_page(html, "https://www.filmweb.pl/film/Incepcja-2010-500891", "Filmweb")
        self.assertEqual((movie.title, movie.original_title, movie.year, movie.rating), ("Incepcja", "Inception", 2010, "8.2"))
        self.assertEqual(match_score(MovieQuery("x.mkv", "Inception", 2010), movie), 1.0)
        self.assertEqual(match_score(MovieQuery("x.mkv", "Inception", 2009), movie), 0.0)

    def test_invalid_page_is_not_fabricated(self):
        with self.assertRaises(ProviderError):
            parse_movie_page("<h1>Access denied</h1>", "https://www.imdb.com/title/tt1375666", "IMDb")

    def test_url_validation(self):
        self.assertEqual(validate_movie_url("https://imdb.com/title/tt1375666/?ref_=x", "IMDb"), "https://www.imdb.com/title/tt1375666")
        for url in ("http://www.imdb.com/title/tt1", "https://imdb.com.evil.test/title/tt1", "https://localhost/title/tt1", "https://www.imdb.com:8443/title/tt1", "https://user@www.imdb.com/title/tt1"):
            with self.subTest(url=url), self.assertRaises(ProviderError):
                validate_movie_url(url, "IMDb")

    def test_ambiguous_search_needs_manual_choice(self):
        provider = WebProvider("IMDb", Mock())
        try:
            with patch.object(provider, "fetch", return_value='<a href="/title/tt1/">One</a><a href="/title/tt2/">Two</a>'), patch.object(provider, "get_movie", side_effect=[
                MovieData("Movie", "https://www.imdb.com/title/tt1", "IMDb", 2000),
                MovieData("Movie", "https://www.imdb.com/title/tt2", "IMDb", 2000),
            ]):
                with self.assertRaisesRegex(ProviderError, "Niejednoznaczne"):
                    provider.search(MovieQuery("Movie.mkv", "Movie"))
        finally:
            provider.close()

    def test_filmweb_search_uses_hits_and_ignores_serials(self):
        cache = Mock()
        cache.get.return_value = None
        provider = WebProvider("Filmweb", cache)
        try:
            payload = json.dumps({"searchHits": [{"id": 500891, "type": "film", "matchedTitle": "Inception"}, {"id": 123, "type": "serial", "matchedTitle": "Inception"}]})
            movie = MovieData("Incepcja", "https://www.filmweb.pl/film/Incepcja-2010-500891", "Filmweb", year=2010, original_title="Inception", description="Opis testowy.")
            preview = json.dumps({"title": {"title": "Incepcja"}, "year": 2010})
            with patch.object(provider, "fetch", side_effect=[payload, preview]) as fetch, patch.object(provider, "get_movie", return_value=movie) as get_movie:
                result = provider.search(MovieQuery("Inception.mkv", "Inception", 2010))
                self.assertIs(result, movie)
                self.assertIn("/api/v1/live/search?query=Inception", fetch.call_args_list[0].args[0])
                get_movie.assert_called_once_with("https://www.filmweb.pl/film/Incepcja-2010-500891")
        finally:
            provider.close()


class ServiceTests(unittest.TestCase):
    def make_service(self):
        service = MovieService.__new__(MovieService)
        service.cancelled = lambda: False
        filmweb, imdb = Mock(source="Filmweb"), Mock(source="IMDb")
        service.providers = [filmweb, imdb]
        return service, filmweb, imdb

    def test_filmweb_description_stops_fallback(self):
        service, filmweb, imdb = self.make_service()
        filmweb.search.return_value = MovieData("Film", "https://www.filmweb.pl/film/Film-2000-1", "Filmweb", description="Opis")
        result = service.lookup(MovieQuery("Film.mkv", "Film"))
        self.assertEqual(result.status, "Znaleziono")
        imdb.search.assert_not_called()

    def test_missing_description_keeps_both_sources(self):
        service, filmweb, imdb = self.make_service()
        filmweb.search.return_value = MovieData("Film", "https://www.filmweb.pl/film/Film-2000-1", "Filmweb", year=2000, original_title="Movie", rating="7.0")
        imdb.search.return_value = MovieData("Movie", "https://www.imdb.com/title/tt1", "IMDb", description="Plot", rating="7.1")
        result = service.lookup(MovieQuery("Movie.mkv", "Movie"))
        self.assertEqual(len(result.entries), 2)
        self.assertEqual(result.description_entry.source, "IMDb")
        self.assertEqual(imdb.search.call_args.args[0].year, 2000)

    def test_failure_of_first_provider_does_not_stop_second(self):
        service, filmweb, imdb = self.make_service()
        filmweb.search.side_effect = ProviderError("HTTP 403")
        imdb.search.return_value = MovieData("Movie", "https://www.imdb.com/title/tt1", "IMDb", description="Plot")
        result = service.lookup(MovieQuery("Movie.mkv", "Movie"))
        self.assertEqual(result.status, "Znaleziono")
        self.assertIn("HTTP 403", result.notes[0])

    def test_manual_link_fallback_uses_selected_movie(self):
        service, filmweb, imdb = self.make_service()
        filmweb.get_movie.return_value = MovieData("Poprawny film", "https://www.filmweb.pl/film/Film-2000-1", "Filmweb", year=2000, original_title="Correct movie")
        imdb.search.return_value = None
        service.lookup(MovieQuery("bad.mkv", "Wrong title", 2020), "https://www.filmweb.pl/film/Film-2000-1")
        query = imdb.search.call_args.args[0]
        self.assertEqual((query.title, query.year), ("Correct movie", 2000))


class ReportAndCacheTests(unittest.TestCase):
    def test_report_escapes_untrusted_text_and_marks_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raport.html"
            movie = MovieData("<script>alert(1)</script>", "https://www.imdb.com/title/tt1", "IMDb", description="<img src=x>", genres=["Drama"], rating="8.0")
            result = MovieResult(MovieQuery("A&B.mkv", "Film"), [movie])
            write_report(path, Path("lista.txt"), [result], partial=True)
            html = path.read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;", html)
            self.assertNotIn("<script>alert", html)
            self.assertIn("&lt;img src=x&gt;", html)
            self.assertIn("A&amp;B.mkv", html)
            self.assertIn("Raport częściowy", html)
            self.assertIn("Dramat", html)
            self.assertIn("IMDb: 8.0 / 10", html)

    def test_missing_data_is_visible_in_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raport.html"
            write_report(path, Path("lista.txt"), [MovieResult(MovieQuery("Film.mkv", "Film"), notes=["Brak dostępu."])])
            html = path.read_text(encoding="utf-8")
            self.assertIn("Brak opisu", html)
            self.assertIn("Brak dostępu", html)

    def test_cache_expiration_and_disabled_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.sqlite3"
            cache = MovieCache(path)
            try:
                cache.put("url", {"title": "Film"})
                self.assertEqual(cache.get("url"), {"title": "Film"})
                cache.connection.execute("UPDATE movies SET fetched = 0")
                cache.connection.commit()
                self.assertIsNone(cache.get("url"))
                cache.enabled = False
                cache.put("other", {"title": "Other"})
                self.assertIsNone(cache.get("other"))
            finally:
                cache.close()


if __name__ == "__main__":
    unittest.main()

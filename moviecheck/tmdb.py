"""Oficjalne API TMDB: niezależne oceny, opisy i plakaty w rozmiarze w500."""

import math
import os
import re
from dataclasses import asdict
from urllib.parse import urlencode

import httpx

from .models import MovieData
from .providers import ProviderError, match_score, search_title_variants, validate_movie_url


class TMDBProvider:
    source = "TMDB"

    def __init__(self, cache, credential="", cancelled=lambda: False):
        self.cache = cache
        self.cancelled = cancelled
        self.credential = credential or os.environ.get("TMDB_READ_ACCESS_TOKEN", "") or os.environ.get("TMDB_API_KEY", "")
        self.batch_state = vars(cache).get("batch_state")
        self.imdb_id = ""
        self.client = httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False)

    def close(self):
        self.client.close()

    def request(self, path, **parameters):
        if not self.credential:
            raise ProviderError("Wpisz token lub klucz API TMDB, aby pobrać ocenę i okładkę.")
        if self.cancelled():
            raise ProviderError("Anulowano.")
        parameters = {"language": "pl-PL", **parameters}
        cache_key = "tmdb:" + path + "?" + urlencode(parameters)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        headers = {}
        if re.fullmatch(r"[a-fA-F0-9]{32}", self.credential):
            parameters["api_key"] = self.credential
        else:
            headers["Authorization"] = "Bearer " + self.credential
        try:
            if self.batch_state:
                self.batch_state.wait_for_request("api.themoviedb.org", self.cancelled)
            if self.cancelled():
                raise ProviderError("Anulowano.")
            response = self.client.get("https://api.themoviedb.org/3" + path, params=parameters, headers=headers)
            if response.status_code in (401, 403):
                raise ProviderError("TMDB: nieprawidłowy token lub brak uprawnień API.")
            if response.status_code == 429:
                raise ProviderError("TMDB: limit zapytań. Spróbuj później lub zmniejsz liczbę równoległych zadań.")
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError("invalid payload")
        except httpx.HTTPError as error:
            raise ProviderError("Błąd połączenia TMDB: " + type(error).__name__ + ".") from None
        except ValueError:
            raise ProviderError("Nierozpoznana odpowiedź TMDB.") from None
        self.cache.put(cache_key, data)
        return data

    @staticmethod
    def movie(data):
        movie_id = data.get("id")
        if not isinstance(movie_id, int) or isinstance(movie_id, bool) or movie_id <= 0:
            raise ProviderError("TMDB nie zawiera identyfikatora filmu.")
        release = str(data.get("release_date") or "")
        year = int(release[:4]) if re.match(r"^\d{4}-", release) else None
        average = data.get("vote_average")
        votes = data.get("vote_count", 0)
        rating = ""
        if isinstance(average, (int, float)) and math.isfinite(average) and 0 <= average <= 10 and isinstance(votes, int) and votes > 0:
            rating = f"{average:.2f}".rstrip("0").rstrip(".") if average else "0"
        poster = data.get("poster_path") or ""
        poster_url = "https://image.tmdb.org/t/p/w500" + poster if isinstance(poster, str) and re.fullmatch(r"/[A-Za-z0-9_.-]+\.(?:jpg|png|webp)", poster) else ""
        genres = [str(item["name"]) for item in data.get("genres", []) if isinstance(item, dict) and item.get("name")]
        return MovieData(str(data.get("title") or data.get("original_title") or ""),
                         f"https://www.themoviedb.org/movie/{movie_id}", "TMDB", year=year,
                         original_title=str(data.get("original_title") or ""), description=str(data.get("overview") or ""),
                         rating=rating, poster_url=poster_url, genres=genres, rating_source="TMDB — vote_average")

    def search(self, query):
        if self.imdb_id:
            data = self.request("/find/" + self.imdb_id, external_source="imdb_id")
            hits = data.get("movie_results", [])
            if len(hits) == 1:
                movie = self.movie(hits[0])
                if not query.year or movie.year == query.year:
                    return self.get_movie(movie.url)
        for title in search_title_variants(query.title):
            parameters = {"query": title, "include_adult": "false"}
            if query.year:
                parameters["year"] = query.year
            data = self.request("/search/movie", **parameters)
            ranked = {}
            for hit in data.get("results", []):
                if not isinstance(hit, dict):
                    continue
                movie = self.movie(hit)
                if movie.title:
                    ranked[movie.url] = (match_score(query, movie), movie)
            ordered = sorted(ranked.values(), key=lambda item: item[0], reverse=True)
            if not ordered or ordered[0][0] < 0.78:
                continue
            if len(ordered) > 1 and ordered[0][0] - ordered[1][0] < 0.08:
                raise ProviderError("Niejednoznaczne dopasowanie TMDB — wskaż link właściwego filmu.")
            return self.get_movie(ordered[0][1].url)
        return None

    def get_movie(self, url):
        url = validate_movie_url(url, "TMDB")
        cached = self.cache.get(url)
        if cached:
            return MovieData(**cached)
        movie_id = re.search(r"/movie/(\d+)", url).group(1)
        data = self.request("/movie/" + movie_id)
        movie = self.movie(data)
        if not movie.description:
            fallback = self.request("/movie/" + movie_id, language="en-US")
            movie.description = str(fallback.get("overview") or "")
        self.cache.put(url, asdict(movie))
        return movie

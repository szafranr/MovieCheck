import csv
import gzip
import json
import re
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

import httpx

from .models import MovieData, MovieQuery
from .providers import ProviderError, WebProvider, image_url, match_score, normalized_title, search_title_variants, validate_movie_url

RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"


class IMDbRatings:
    def __init__(self, cache, cancelled=lambda: False, status=lambda message: None):
        self.cache = cache
        self.cancelled = cancelled
        self.status = status
        self.failure = ""
        self.refreshed = False

    def import_ratings(self, path: Path):
        connection = self.cache.connection
        with gzip.open(path, "rt", encoding="utf-8", newline="") as source, connection:
            reader = csv.DictReader(source, delimiter="\t")
            if reader.fieldnames != ["tconst", "averageRating", "numVotes"]:
                raise ProviderError("Nierozpoznany format oficjalnego zbioru ocen IMDb.")
            connection.execute("DROP TABLE IF EXISTS imdb_ratings_next")
            connection.execute("CREATE TABLE imdb_ratings_next (id TEXT PRIMARY KEY, rating TEXT NOT NULL, votes INTEGER NOT NULL)")
            batch = []
            count = 0
            for row in reader:
                if not re.fullmatch(r"tt\d+", row["tconst"]) or not 0 <= float(row["averageRating"]) <= 10:
                    raise ProviderError("Nieprawidłowy rekord w zbiorze ocen IMDb.")
                batch.append((row["tconst"], row["averageRating"], int(row["numVotes"])))
                count += 1
                if len(batch) == 10000:
                    if self.cancelled():
                        raise ProviderError("Anulowano.")
                    connection.executemany("INSERT INTO imdb_ratings_next VALUES (?, ?, ?)", batch)
                    batch.clear()
            if batch:
                connection.executemany("INSERT INTO imdb_ratings_next VALUES (?, ?, ?)", batch)
            if not count or self.cancelled():
                raise ProviderError("Przerwano przygotowanie zbioru ocen IMDb.")
            connection.execute("DROP TABLE IF EXISTS imdb_ratings")
            connection.execute("ALTER TABLE imdb_ratings_next RENAME TO imdb_ratings")
            connection.execute("CREATE TABLE IF NOT EXISTS imdb_metadata (key TEXT PRIMARY KEY, value REAL)")
            connection.execute("INSERT OR REPLACE INTO imdb_metadata VALUES ('fetched', ?)", (time.time(),))

    def download(self):
        self.status("Przygotowywanie niezależnych ocen IMDb — pobieranie bazy")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.cache.path.parent, suffix=".tsv.gz", delete=False) as output:
                temporary = Path(output.name)
                size = 0
                with httpx.stream("GET", RATINGS_URL, timeout=30, follow_redirects=False) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        if self.cancelled():
                            raise ProviderError("Anulowano.")
                        size += len(chunk)
                        if size > 100 * 1024 * 1024:
                            raise ProviderError("Zbiór ocen IMDb przekracza dopuszczalny rozmiar.")
                        output.write(chunk)
            self.status("Przygotowywanie niezależnych ocen IMDb — indeksowanie bazy")
            self.import_ratings(temporary)
        except (httpx.HTTPError, OSError, ValueError, EOFError) as error:
            raise ProviderError(f"Nie udało się przygotować zbioru ocen IMDb: {type(error).__name__}.") from error
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)

    def get(self, movie_id: str) -> str:
        if self.failure:
            raise ProviderError(self.failure)
        connection = self.cache.connection
        connection.execute("CREATE TABLE IF NOT EXISTS imdb_metadata (key TEXT PRIMARY KEY, value REAL)")
        connection.commit()
        row = connection.execute("SELECT value FROM imdb_metadata WHERE key = 'fetched'").fetchone()
        if not row or time.time() - row[0] > 7 * 86400 or (not self.cache.enabled and not self.refreshed):
            try:
                self.download()
                self.refreshed = True
            except ProviderError as error:
                if not self.cancelled():
                    self.failure = str(error)
                raise
        row = connection.execute("SELECT rating FROM imdb_ratings WHERE id = ?", (movie_id,)).fetchone()
        return row[0] if row else ""


class IMDbProvider(WebProvider):
    def __init__(self, cache, cancelled=lambda: False, status=lambda message: None):
        super().__init__("IMDb", cache, cancelled)
        self.ratings = IMDbRatings(cache, cancelled, status)
        self.suggestions = {}
        self.pages_unavailable = False

    def search(self, query: MovieQuery) -> MovieData | None:
        for title in search_title_variants(query.title):
            if self.cancelled():
                raise ProviderError("Anulowano.")
            try:
                data = json.loads(self.fetch("https://v3.sg.media-imdb.com/suggestion/x/" + quote(title.lower(), safe="") + ".json"))
                hits = data.get("d", [])
                if not isinstance(hits, list):
                    raise ValueError("invalid suggestions")
            except (ValueError, AttributeError) as error:
                raise ProviderError("Nierozpoznane wyniki wyszukiwania IMDb.") from error
            ranked = {}
            for hit in hits:
                if not isinstance(hit, dict) or not re.fullmatch(r"tt\d+", str(hit.get("id", ""))) or hit.get("qid") not in ("movie", "tvMovie"):
                    continue
                year = hit.get("y")
                image = hit.get("i")
                movie = MovieData(str(hit.get("l") or ""), "https://www.imdb.com/title/" + hit["id"], "IMDb",
                                  year=year if isinstance(year, int) else None, poster_url=image_url(image.get("imageUrl")) if isinstance(image, dict) else "")
                if not movie.title:
                    continue
                score = match_score(query, movie)
                # IMDb może wyświetlać tytuł bez podtytułu (np. Glass Onion).
                # Taki alias wymaga identycznego tytułu głównego i znanego,
                # zgodnego roku; nie skracamy ogólnie wszystkich zapytań.
                main_title, separator, _ = query.title.partition(":")
                if separator and len(normalized_title(main_title)) >= 8 and query.year and movie.year == query.year and normalized_title(main_title) == normalized_title(movie.title):
                    score = 1.0
                if score >= 0.78:
                    ranked[movie.url] = (score, movie)
            ordered = sorted(ranked.values(), key=lambda item: item[0], reverse=True)
            confirmed_year = [item for item in ordered if query.year and item[1].year == query.year]
            if confirmed_year:
                ordered = confirmed_year
            if not ordered:
                continue
            if len(ordered) > 1 and ordered[0][0] - ordered[1][0] < 0.08:
                raise ProviderError("Niejednoznaczne dopasowanie IMDb — wskaż link właściwego filmu.")
            movie = ordered[0][1]
            self.suggestions[movie.url] = movie
            return self.get_movie(movie.url)
        return None

    def get_movie(self, url: str) -> MovieData:
        url = validate_movie_url(url, "IMDb")
        movie_id = url.rsplit("/", 1)[-1]
        cached = self.cache.get(url)
        if cached and cached.get("rating"):
            if cached.get("rating_source") == "IMDb — oficjalny zbiór ocen":
                return self.dataset_movie(MovieData(**cached))
            return MovieData(**cached)
        if not self.pages_unavailable:
            try:
                movie = super().get_movie(url)
                if movie.rating:
                    movie.rating_source = "IMDb — strona filmu"
                    return movie
            except ProviderError:
                if self.cancelled():
                    raise
                self.pages_unavailable = True
                movie = None
        else:
            movie = None
        movie = movie or self.suggestions.get(url) or MovieData("Film IMDb " + movie_id, url, "IMDb")
        return self.dataset_movie(movie)

    def dataset_movie(self, movie: MovieData) -> MovieData:
        movie_id = movie.url.rsplit("/", 1)[-1]
        try:
            movie.rating = self.ratings.get(movie_id)
            movie.rating_source = "IMDb — oficjalny zbiór ocen"
        except ProviderError as error:
            if self.cancelled():
                raise
            movie.rating = ""
            movie.provider_notes.append(str(error))
        if movie.rating and not movie.title.startswith("Film IMDb tt"):
            self.cache.put(movie.url, asdict(movie))
        return movie

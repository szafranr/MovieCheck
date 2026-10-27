"""Opcjonalna diagnostyka połączeń z serwisami (wykonuje żądania sieciowe)."""

import json
import tempfile
from pathlib import Path

from moviecheck.cache import MovieCache
from moviecheck.models import MovieQuery
from moviecheck.providers import ProviderError, WebProvider


def main():
    with tempfile.TemporaryDirectory() as directory:
        cache = MovieCache(Path(directory) / "cache.sqlite3", enabled=False)
        for source, url in (
            ("Filmweb", "https://www.filmweb.pl/film/Incepcja-2010-500891"),
            ("IMDb", "https://www.imdb.com/title/tt1375666"),
        ):
            provider = WebProvider(source, cache)
            try:
                for operation, action in (
                    ("direct", lambda: provider.get_movie(url)),
                    ("search", lambda: provider.search(MovieQuery("Inception.2010.mkv", "Inception", 2010))),
                ):
                    try:
                        movie = action()
                        print(json.dumps({"source": source, "operation": operation, "found": bool(movie),
                                          "year": movie.year if movie else None,
                                          "has_description": bool(movie and movie.description),
                                          "has_rating": bool(movie and movie.rating)}, ensure_ascii=False), flush=True)
                    except (ProviderError, ValueError) as error:
                        print(json.dumps({"source": source, "operation": operation, "error": str(error)}, ensure_ascii=False), flush=True)
            finally:
                provider.close()
        cache.close()


if __name__ == "__main__":
    main()

from .models import MovieQuery, MovieResult
from .providers import ProviderError, WebProvider


class MovieService:
    def __init__(self, cache, cancelled=lambda: False):
        self.providers = [WebProvider("Filmweb", cache, cancelled), WebProvider("IMDb", cache, cancelled)]
        self.cancelled = cancelled

    def close(self):
        for provider in self.providers:
            provider.close()

    def lookup(self, query: MovieQuery, override: str = "") -> MovieResult:
        result = MovieResult(query)
        if override:
            from urllib.parse import urlsplit

            hostname = urlsplit(override).hostname
            providers = [provider for provider in self.providers if hostname in ({"filmweb.pl", "www.filmweb.pl"} if provider.source == "Filmweb" else {"imdb.com", "www.imdb.com"})]
            if not providers:
                result.notes.append("Nieobsługiwany adres. Wskaż stronę filmu Filmweb lub IMDb.")
                return result
            selected = providers[0]
            # Po ręcznym wskazaniu Filmweb zachowaj uzupełnianie opisu z IMDb.
            providers = [selected] + ([self.providers[1]] if selected.source == "Filmweb" else [])
        else:
            providers = self.providers
        lookup_query = query
        for index, provider in enumerate(providers):
            if self.cancelled():
                break
            try:
                movie = provider.get_movie(override) if override and index == 0 else provider.search(lookup_query)
                if movie:
                    result.entries.append(movie)
                    if movie.description:
                        break
                    # Uzupełniaj dane rozpoznanego filmu, także po ręcznej korekcie linku.
                    lookup_query = MovieQuery(query.filename, movie.original_title or movie.title, movie.year or query.year)
                else:
                    result.notes.append(f"{provider.source}: brak pewnego dopasowania tytułu i roku.")
            except (ProviderError, ValueError) as error:
                result.notes.append(f"{provider.source}: {error}")
        return result

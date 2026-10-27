from .models import MovieQuery, MovieResult
from .providers import ProviderError, WebProvider
from .imdb import IMDbProvider
from .vod import FilmwebVod


class MovieService:
    def __init__(self, cache, cancelled=lambda: False, status=lambda message: None):
        self.providers = [WebProvider("Filmweb", cache, cancelled), IMDbProvider(cache, cancelled, status)]
        self.cancelled = cancelled
        self.vod = FilmwebVod(cache, self.providers[0].fetch)

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
            providers = [selected] + [provider for provider in self.providers if provider is not selected]
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
                    result.notes.extend(f"{provider.source}: {note}" for note in movie.provider_notes)
                    # Każdy dostawca jest sprawdzany niezależnie od obecności
                    # opisu. Zachowaj tożsamość filmu po ręcznej korekcie linku.
                    if not movie.title.startswith("Film IMDb tt"):
                        lookup_query = MovieQuery(query.filename, movie.original_title or movie.title, movie.year or query.year)
                else:
                    result.notes.append(f"{provider.source}: brak pewnego dopasowania tytułu i roku.")
            except (ProviderError, ValueError) as error:
                result.notes.append(f"{provider.source}: {error}")
        result.entries.sort(key=lambda movie: movie.source != "Filmweb")
        filmweb = result.entry_for("Filmweb")
        if filmweb and not self.cancelled():
            try:
                result.vod = self.vod.lookup(filmweb.url)
            except (ProviderError, ValueError) as error:
                result.notes.append(f"Filmweb VOD: {error}")
        return result

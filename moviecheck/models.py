from dataclasses import dataclass, field


@dataclass
class MovieQuery:
    filename: str
    title: str
    year: int | None = None


@dataclass
class MovieData:
    title: str
    url: str
    source: str
    year: int | None = None
    original_title: str = ""
    description: str = ""
    genres: list[str] = field(default_factory=list)
    rating: str = ""
    rating_scale: str = "10"
    poster_url: str = ""
    rating_source: str = ""
    provider_notes: list[str] = field(default_factory=list)


@dataclass
class VodOffer:
    provider_name: str
    url: str
    logo_url: str = ""
    additional_subscription: bool = False


@dataclass
class VodAvailability:
    offers: list[VodOffer] = field(default_factory=list)
    checked_at: str = ""


@dataclass
class MovieResult:
    query: MovieQuery
    entries: list[MovieData] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    vod: VodAvailability = field(default_factory=VodAvailability)

    def entry_for(self, source: str) -> MovieData | None:
        return next((entry for entry in self.entries if entry.source == source), None)

    @property
    def primary(self) -> MovieData | None:
        return self.description_entry or (self.entries[0] if self.entries else None)

    @property
    def description_entry(self) -> MovieData | None:
        return next((entry for source in ("Filmweb", "IMDb", "TMDB")
                     for entry in self.entries if entry.source == source and entry.description), None)

    @property
    def poster_entry(self) -> MovieData | None:
        return next((entry for source in ("TMDB", "Filmweb", "IMDb")
                     for entry in self.entries if entry.source == source and entry.poster_url), None)

    @property
    def status(self) -> str:
        if not self.entries:
            return "Wymaga sprawdzenia"
        if not self.description_entry:
            return "Brak opisu"
        return "Znaleziono"

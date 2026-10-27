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


@dataclass
class MovieResult:
    query: MovieQuery
    entries: list[MovieData] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def primary(self) -> MovieData | None:
        return self.entries[0] if self.entries else None

    @property
    def description_entry(self) -> MovieData | None:
        return next((entry for entry in self.entries if entry.description), None)

    @property
    def status(self) -> str:
        if not self.entries:
            return "Wymaga sprawdzenia"
        if not self.description_entry:
            return "Brak opisu"
        return "Znaleziono"

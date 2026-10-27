import os
import secrets
import tempfile
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from .models import MovieResult
from . import __version__
from .providers import image_url

GENRE_NAMES = {
    "action": "Akcja", "adventure": "Przygodowy", "animation": "Animacja", "biography": "Biograficzny",
    "comedy": "Komedia", "crime": "Kryminał", "documentary": "Dokumentalny", "drama": "Dramat",
    "family": "Familijny", "fantasy": "Fantasy", "film-noir": "Film noir", "history": "Historyczny",
    "horror": "Horror", "music": "Muzyczny", "musical": "Musical", "mystery": "Tajemnica",
    "romance": "Romans", "sci-fi": "Sci-Fi", "science fiction": "Sci-Fi", "short": "Krótkometrażowy",
    "sport": "Sportowy", "thriller": "Thriller", "war": "Wojenny", "western": "Western",
}


def translate_genres(genres: list[str]) -> str:
    return ", ".join(GENRE_NAMES.get(genre.casefold(), genre) for genre in genres)


def write_report(path: Path, source: Path, results: list[MovieResult], partial: bool = False):
    environment = Environment(loader=PackageLoader("moviecheck", "templates"), autoescape=select_autoescape(["html"]))
    environment.filters["genres"] = translate_genres
    environment.filters["image_url"] = image_url
    content = environment.get_template("report.html").render(
        source=source.name, results=results, partial=partial, script_nonce=secrets.token_urlsafe(18), app_version=__version__,
        generated=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        found=sum(bool(result.entries) for result in results),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(content)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()

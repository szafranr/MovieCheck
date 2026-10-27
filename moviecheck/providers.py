import json
import re
import time
import unicodedata
from dataclasses import asdict
from difflib import SequenceMatcher
from urllib.parse import quote, urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from .models import MovieData, MovieQuery


class ProviderError(Exception):
    pass


def normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold().replace("ł", "l"))
    return " ".join(re.sub(r"[^\w\s]", " ", "".join(char for char in value if not unicodedata.combining(char))).split())


def match_score(query: MovieQuery, movie: MovieData) -> float:
    titles = [movie.title, movie.original_title]
    score = max(SequenceMatcher(None, normalized_title(query.title), normalized_title(title)).ratio() for title in titles if title)
    if query.year and movie.year and query.year != movie.year:
        return 0.0
    return score


def validate_movie_url(url: str, source: str) -> str:
    parts = urlsplit(url)
    hosts = {"Filmweb": {"filmweb.pl", "www.filmweb.pl"}, "IMDb": {"imdb.com", "www.imdb.com"}}
    pattern = r"/film/[^/]+-\d+" if source == "Filmweb" else r"/title/tt\d+"
    if parts.scheme != "https" or parts.hostname not in hosts.get(source, set()) or parts.port not in (None, 443) or parts.username or parts.password or not re.fullmatch(pattern + r"/?", parts.path):
        raise ProviderError("Podaj pełny adres HTTPS strony filmu z Filmweb lub IMDb.")
    return f"https://www.{('filmweb.pl' if source == 'Filmweb' else 'imdb.com')}{parts.path.rstrip('/')}"


def movie_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from movie_objects(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if "Movie" in types:
            yield value
        if "@graph" in value:
            yield from movie_objects(value["@graph"])


def parse_filmweb_page(soup: BeautifulSoup, url: str) -> MovieData:
    title = soup.select_one("h1[itemprop='name'], h1.filmCoverSection__title")
    if not title:
        raise ProviderError("Strona nie zawiera rozpoznawalnego tytułu filmu Filmweb. Możliwa zmiana strony lub blokada dostępu.")

    def text(selector: str) -> str:
        element = soup.select_one(selector)
        return str(element.get("content") or element.get_text(" ", strip=True)).strip() if element else ""

    year_text = text(".filmCoverSection__year")
    year_match = re.search(r"\b(?:18|19|20)\d{2}\b", year_text)
    if not year_match:
        year_match = re.search(r"-(\d{4})-\d+$", url)
    year = int(year_match.group(1) if year_match.lastindex else year_match.group()) if year_match else None
    original_title = text(".filmCoverSection__originalTitle")
    if year:
        original_title = re.sub(rf"\s*\(?{year}\)?\s*$", "", original_title).strip()
    description = text("[itemprop='description']") or text(".filmPosterSection__plot")
    genres = list(dict.fromkeys(element.get_text(" ", strip=True) for element in soup.select("[itemprop='genre']")))
    return MovieData(title=title.get_text(" ", strip=True), url=validate_movie_url(url, "Filmweb"), source="Filmweb",
                     year=year, original_title=original_title, description=description, genres=genres,
                     rating=text("[itemprop='aggregateRating'] [itemprop='ratingValue']"),
                     rating_scale=text("[itemprop='aggregateRating'] [itemprop='bestRating']") or "10")


def parse_movie_page(html: str, url: str, source: str) -> MovieData:
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.find("link", rel="canonical", href=True)
    if canonical:
        url = validate_movie_url(urljoin(url, canonical["href"]), source)
    data = None
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = next(movie_objects(json.loads(script.get_text())), None)
        except (ValueError, TypeError):
            continue
        if data:
            break
    if (not data or not data.get("name")) and source == "Filmweb":
        return parse_filmweb_page(soup, url)
    if not data or not data.get("name"):
        raise ProviderError("Strona nie zawiera rozpoznawalnych danych filmu (JSON-LD). Możliwa zmiana strony lub blokada dostępu.")
    title = BeautifulSoup(str(data["name"]), "html.parser").get_text(" ", strip=True)
    description = BeautifulSoup(str(data.get("description") or ""), "html.parser").get_text(" ", strip=True)
    genres = data.get("genre") or []
    if isinstance(genres, str):
        genres = [part.strip() for part in genres.split(",") if part.strip()]
    if not isinstance(genres, list):
        genres = []
    rating = data.get("aggregateRating") or {}
    if not isinstance(rating, dict):
        rating = {}
    release = str(data.get("datePublished") or "")
    year_match = re.search(r"\b(?:18|19|20)\d{2}\b", release)
    if not year_match:
        year_match = re.search(r"-(\d{4})-\d+$", url)
    alternative = data.get("alternateName") or ""
    if isinstance(alternative, list):
        alternative = next((name for name in alternative if isinstance(name, str)), "")
    return MovieData(title=title, url=validate_movie_url(url, source), source=source,
                     year=int(year_match.group(1) if year_match.lastindex else year_match.group()) if year_match else None,
                     original_title=str(alternative), description=description,
                     genres=[str(genre) for genre in genres], rating=str(rating.get("ratingValue") or ""),
                     rating_scale=str(rating.get("bestRating") or "10"))


class WebProvider:
    def __init__(self, source: str, cache, cancelled=lambda: False):
        self.source = source
        self.cache = cache
        self.cancelled = cancelled
        self.last_request = 0.0
        self.client = httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=False,
                                   headers={"User-Agent": "MovieCheck/0.1 (+local desktop movie catalog)", "Accept-Language": "pl,en;q=0.8"})

    def close(self):
        self.client.close()

    def fetch(self, url: str) -> str:
        for _ in range(4):
            while time.monotonic() - self.last_request < 1.1:
                if self.cancelled():
                    raise ProviderError("Anulowano.")
                time.sleep(0.05)
            if self.cancelled():
                raise ProviderError("Anulowano.")
            self.last_request = time.monotonic()
            try:
                response = self.client.get(url)
                if response.status_code in (301, 302, 303, 307, 308):
                    redirected = urljoin(url, response.headers.get("location", ""))
                    domain = "filmweb.pl" if self.source == "Filmweb" else "imdb.com"
                    parts = urlsplit(redirected)
                    if parts.scheme != "https" or parts.hostname not in (domain, "www." + domain) or parts.port not in (None, 443) or parts.username or parts.password:
                        raise ProviderError("Serwis przekierował żądanie poza dozwoloną domenę.")
                    url = redirected
                    continue
                if response.status_code in (403, 429):
                    raise ProviderError(f"Serwis odmówił dostępu (HTTP {response.status_code}). Spróbuj później lub otwórz film w przeglądarce.")
                response.raise_for_status()
                if not response.text.strip():
                    raise ProviderError(f"Serwis zwrócił pustą odpowiedź (HTTP {response.status_code}). Dane nie są obecnie dostępne.")
                return response.text
            except httpx.HTTPStatusError as error:
                raise ProviderError(f"Serwis zwrócił błąd HTTP {error.response.status_code}.") from error
            except httpx.HTTPError as error:
                # Nie umieszczaj całych odpowiedzi sieciowych w raporcie.
                raise ProviderError(f"Błąd połączenia: {type(error).__name__}.") from error
        raise ProviderError("Zbyt wiele przekierowań.")

    def get_movie(self, url: str) -> MovieData:
        url = validate_movie_url(url, self.source)
        cached = self.cache.get(url)
        if cached:
            return MovieData(**cached)
        movie = parse_movie_page(self.fetch(url), url, self.source)
        self.cache.put(url, asdict(movie))
        return movie

    def filmweb_url(self, movie_id: str) -> str:
        preview_url = f"https://www.filmweb.pl/api/v1/film/{movie_id}/preview"
        preview = self.cache.get(preview_url)
        if not preview:
            try:
                preview = json.loads(self.fetch(preview_url))
            except ValueError as error:
                raise ProviderError("Nierozpoznana odpowiedź podglądu filmu Filmweb.") from error
            if not isinstance(preview, dict):
                raise ProviderError("Podgląd filmu Filmweb nie zawiera danych.")
            self.cache.put(preview_url, preview)
        title = preview.get("title") or preview.get("originalTitle") or {}
        title = title.get("title", "") if isinstance(title, dict) else str(title)
        year = preview.get("year")
        if not title or not str(year).isdigit():
            raise ProviderError("Podgląd filmu Filmweb nie zawiera tytułu lub roku.")
        slug = quote(title.replace(" ", "+"), safe="+")
        return f"https://www.filmweb.pl/film/{slug}-{year}-{movie_id}"

    def search(self, query: MovieQuery) -> MovieData | None:
        search_title = query.title + (f" {query.year}" if query.year else "")
        if self.source == "Filmweb":
            base = "https://www.filmweb.pl"
            # Publiczne wyszukiwanie używane przez witrynę; HTML wyszukiwarki
            # zawiera rekomendacje zamiast właściwych wyników ładowanych przez JS.
            url = base + "/api/v1/live/search?query=" + quote(query.title)
            try:
                hits = json.loads(self.fetch(url)).get("searchHits", [])
            except (ValueError, AttributeError) as error:
                raise ProviderError("Nierozpoznana odpowiedź wyszukiwarki Filmweb.") from error
            candidates = []
            for hit in hits:
                if not isinstance(hit, dict) or hit.get("type") != "film" or not str(hit.get("id", "")).isdigit():
                    continue
                candidate = str(hit["id"])
                if candidate not in candidates:
                    candidates.append(candidate)
        else:
            base = "https://www.imdb.com"
            url = base + "/find/?s=tt&ttype=ft&q=" + quote(search_title)
            pattern = re.compile(r"^/title/tt\d+/?$")
            soup = BeautifulSoup(self.fetch(url), "html.parser")
            candidates = []
            for anchor in soup.find_all("a", href=True):
                parts = urlsplit(urljoin(base, anchor["href"]))
                if parts.hostname != urlsplit(base).hostname or not pattern.fullmatch(parts.path):
                    continue
                candidate = base + parts.path.rstrip("/")
                if candidate not in candidates:
                    candidates.append(candidate)
        if not candidates:
            raise ProviderError("Brak odczytywalnych wyników wyszukiwania. Strona może wymagać JavaScript. Użyj przycisku „Wskaż link filmu”.")
        ranked = []
        failures = []
        for candidate in candidates[:5]:
            if self.cancelled():
                raise ProviderError("Anulowano.")
            try:
                if self.source == "Filmweb":
                    candidate = self.filmweb_url(candidate)
                movie = self.get_movie(candidate)
                ranked.append((match_score(query, movie), movie))
            except ProviderError as error:
                failures.append(str(error))
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked and failures:
            raise ProviderError(failures[0])
        if not ranked or ranked[0][0] < 0.78:
            return None
        if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < 0.08:
            raise ProviderError("Niejednoznaczne dopasowanie — wskaż link właściwego filmu.")
        return ranked[0][1]

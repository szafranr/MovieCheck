import re
from pathlib import Path

from .models import MovieQuery

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".mpg", ".mpeg", ".webm", ".ts", ".m2ts", ".vob", ".iso"}
EXTENSION_PATTERN = "|".join(re.escape(extension[1:]) for extension in sorted(VIDEO_EXTENSIONS))
VIDEO_LINE = re.compile(rf"(?i)^(.+\.(?:{EXTENSION_PATTERN}))\s*$")
RELEASE_MARKER = re.compile(
    r"(?ix)\b(?:2160p|1080[pi]|720p|480p|4k|8k|bluray|blu-ray|brrip|bdrip|bdrip|"
    r"web[ ._-]?dl|webrip|hdtv|dvdrip|remux|x26[45]|h[ ._-]?26[45]|hevc|avc|"
    r"aac|ac3|eac3|dts|ddp|hdr10?|dv|repack|proper|multi|dual|lektor|dubbing|napisy)\b"
)


def parse_filename(filename: str) -> MovieQuery:
    basename = re.split(r"[/\\]", filename.strip().strip('"'))[-1]
    title = basename
    if Path(title).suffix.lower() in VIDEO_EXTENSIONS:
        title = title[: -len(Path(title).suffix)]
    title = re.sub(r"[._]+", " ", title)
    marker = RELEASE_MARKER.search(title)
    title_part = title[: marker.start()] if marker else title
    # Rok wewnątrz tytułu (np. „2001 Odyseja kosmiczna”) nie znika.
    years = list(re.finditer(r"(?<!\d)(?:18|19|20)\d{2}(?!\d)", title_part))
    year = None
    if years:
        last_year = years[-1]
        if title_part[: last_year.start()].strip(" ()[]-"):
            year = int(last_year.group())
            title_part = title_part[: last_year.start()]
    title_part = re.sub(r"\[[^\]]*\]", " ", title_part)
    title_part = re.sub(r"\s+", " ", title_part).strip(" -()[]")
    return MovieQuery(filename, title_part or Path(basename).stem, year)


def decode_listing(path: Path) -> str:
    content = path.read_bytes()
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16")
    if b"\x00" in content:
        raise ValueError("Nieobsługiwane kodowanie. Zapisz listę jako UTF-8 lub UTF-16 z BOM.")
    for encoding in ("utf-8-sig", "cp1250"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("Nie można odczytać listy. Zapisz plik w kodowaniu UTF-8.")


def extract_listing_names(content: str) -> list[str]:
    names = []
    for raw_line in content.splitlines():
        line = raw_line.strip().strip('"')
        if not line or line.startswith(("#", "total ", "razem ")):
            continue
        # PowerShell: Mode, LastWriteTime, Length, Name.
        powershell = re.match(r"^[\-ladhrs]{5,}\s+.+?\s+\d+\s+(.+)$", line, re.I)
        # Unix ls -l: uprawnienia, liczba dowiązań, użytkownik, grupa,
        # rozmiar, miesiąc, dzień, godzina/rok, nazwa.
        unix = re.match(r"^[\-l][rwxstST\-]{9}[+@.]?\s+(?:\S+\s+){7}(.+)$", line)
        if powershell:
            line = powershell.group(1)
        elif unix:
            line = unix.group(1)
        match = VIDEO_LINE.match(line)
        if match:
            names.append(match.group(1))
    return names


def load_queries(path: Path, recursive: bool = False) -> list[MovieQuery]:
    if not path.exists():
        raise ValueError("Wskazana ścieżka nie istnieje.")
    if path.is_dir():
        files = path.rglob("*") if recursive else path.iterdir()
        names = [str(item.relative_to(path)) for item in files if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS]
    elif path.suffix.lower() == ".txt":
        names = extract_listing_names(decode_listing(path))
    else:
        raise ValueError("Wybierz katalog lub plik .txt z nazwami filmów.")
    queries = [parse_filename(name) for name in sorted(set(names), key=str.casefold)]
    if not queries:
        raise ValueError("Nie znaleziono nazw plików wideo. Lista powinna zawierać jedną pełną nazwę w wierszu, z rozszerzeniem np. .mkv lub .mp4.")
    return queries


def suggested_report_path(path: Path) -> Path:
    return path.parent / (path.name + ".html") if path.is_dir() else path.with_suffix(".html")

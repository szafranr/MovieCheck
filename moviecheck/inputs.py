import re
from pathlib import Path

from .models import MovieQuery

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".mpg", ".mpeg", ".webm", ".ts", ".m2ts", ".vob", ".iso"}
EXTENSION_PATTERN = "|".join(re.escape(extension[1:]) for extension in sorted(VIDEO_EXTENSIONS))
VIDEO_LINE = re.compile(rf"(?i)^(.+\.(?:{EXTENSION_PATTERN}))\s*$")
NON_MOVIE_EXTENSIONS = {
    ".txt", ".nfo", ".srt", ".ass", ".ssa", ".sub", ".idx", ".vtt", ".sfv", ".cue",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".pdf", ".html", ".htm",
    ".zip", ".rar", ".7z", ".torrent", ".part", ".crdownload", ".exe", ".dll", ".db",
    ".sqlite", ".sqlite3", ".log", ".ini", ".json", ".xml", ".yaml", ".yml", ".md",
    ".doc", ".docx", ".xls", ".xlsx", ".mp3", ".flac", ".wav",
}
SUPPORT_NAMES = {"sample", "samples", "extras", "bonus", "trailers", "subs", "subtitles", "napisy", "bdmv", "certificate", "video_ts", "audio_ts", "@eadir"}
RELEASE_MARKER = re.compile(
    r"(?ix)\b(?:2160p|1080[pi]|720p|480p|4k|8k|bluray|blu-ray|brrip|bdrip|bdrip|"
    r"web[ ._-]?dl|webrip|hdtv|dvdrip|remux|x26[45]|h[ ._-]?26[45]|hevc|avc|"
    r"aac|ac3|eac3|dts|ddp|hdr10?|dv|repack|proper|multi|dual|lektor|dubbing|napisy)\b"
)


def parse_filename(filename: str) -> MovieQuery:
    basename = re.split(r"[/\\]", filename.strip().strip('"').rstrip("/\\"))[-1]
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
    # Kropki w nazwie katalogu nie muszą oznaczać rozszerzenia pliku.
    return MovieQuery(filename, title_part or title.strip(), year)


def is_support_name(name: str) -> bool:
    basename = re.split(r"[/\\]", name.rstrip("/\\"))[-1]
    return basename.startswith(".") or basename.casefold() in SUPPORT_NAMES or bool(re.fullmatch(r"(?i)(?:cd|disc|disk)[ ._-]?\d+", basename))


def is_movie_name(name: str) -> bool:
    basename = re.split(r"[/\\]", name.rstrip("/\\"))[-1]
    return bool(basename) and not is_support_name(basename) and Path(basename).suffix.lower() not in NON_MOVIE_EXTENSIONS


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
        if not line or line.lower().startswith(("#", "directory:", "katalog:")) or re.fullmatch(r"(?i)(?:total|razem)\s+\d+", line):
            continue
        compact = " ".join(line.split())
        if compact == "Mode LastWriteTime Length Name" or re.fullmatch(r"[-\s]+", line):
            continue
        # PowerShell: Mode, LastWriteTime, Length, Name.
        powershell_directory = re.match(r"^d[\-larhs]{4,}\s+\S+\s+\S+(?:\s+(?:AM|PM))?\s+(.+)$", line, re.I)
        powershell = re.match(r"^[\-ladhrs]{5,}\s+.+?\s+\d+\s+(.+)$", line, re.I)
        # Unix ls -l: uprawnienia, liczba dowiązań, użytkownik, grupa,
        # rozmiar, miesiąc, dzień, godzina/rok, nazwa.
        unix = re.match(r"^[\-ld][rwxstST\-]{9}[+@.]?\s+(?:\S+\s+){7}(.+)$", line)
        if unix:
            line = unix.group(1).split(" -> ", 1)[0]
        elif powershell_directory:
            line = powershell_directory.group(1)
        elif powershell:
            line = powershell.group(1)
        elif re.match(r"^[\-ld][\-larhsrwxstST]{4,}\s", line):
            continue
        line = line.strip().strip('"').rstrip("/\\")
        match = VIDEO_LINE.match(line)
        if match:
            names.append(match.group(1))
        elif is_movie_name(line):
            names.append(line)
    return names


def is_movie_directory(path: Path) -> bool:
    if not is_movie_name(path.name):
        return False
    children = [item for item in path.iterdir() if not is_support_name(item.name) and not item.is_symlink()]
    # Folder zawierający kolejne foldery filmów jest kontenerem kolekcji.
    if any(item.is_dir() for item in children):
        return False
    query = parse_filename(path.name)
    if query.year is not None or RELEASE_MARKER.search(path.name.replace(".", " ")):
        return True
    videos = [item for item in children if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS]
    for video in videos:
        video_query = parse_filename(video.name)
        title = video_query.title.casefold()
        if title == query.title.casefold() or (video_query.year is None and title in {"video", "movie", "film", "feature", "main"}):
            return True
    return False


def directory_movie_names(path: Path, recursive: bool) -> list[str]:
    def movie_name(directory: Path) -> str:
        query = parse_filename(directory.name)
        if query.year is None:
            matching = [item for item in directory.iterdir() if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
                        and parse_filename(item.name).title.casefold() == query.title.casefold()]
            years = {parse_filename(item.name).year for item in matching}
            if len(years) == 1 and None not in years:
                return str(sorted(matching)[0].relative_to(path))
        return directory.name if directory == path else str(directory.relative_to(path))

    if is_movie_directory(path):
        return [movie_name(path)]
    names = []
    seen = set()

    def visit(directory: Path):
        resolved = directory.resolve()
        if resolved in seen or not resolved.is_relative_to(path.resolve()):
            return
        seen.add(resolved)
        for item in directory.iterdir():
            if is_support_name(item.name) or item.is_symlink():
                continue
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS:
                names.append(str(item.relative_to(path)))
            elif item.is_dir():
                if is_movie_directory(item):
                    names.append(movie_name(item))
                elif recursive:
                    visit(item)

    visit(path)
    return names


def unique_movie_queries(names: list[str]) -> list[MovieQuery]:
    parsed = [(name, parse_filename(name)) for name in sorted(set(names), key=lambda value: (value.casefold(), value))]
    # Zachowaj osobne pliki wydań, lecz nie dodawaj ponownie odpowiadającego
    # im katalogu, jeśli listing zawiera jednocześnie obie nazwy.
    file_keys = {(query.title.casefold(), query.year) for name, query in parsed if Path(name).suffix.lower() in VIDEO_EXTENSIONS}
    return [query for name, query in parsed if Path(name).suffix.lower() in VIDEO_EXTENSIONS or (query.title.casefold(), query.year) not in file_keys]


def load_queries(path: Path, recursive: bool = False) -> list[MovieQuery]:
    if not path.exists():
        raise ValueError("Wskazana ścieżka nie istnieje.")
    if path.is_dir():
        names = directory_movie_names(path, recursive)
    elif path.suffix.lower() == ".txt":
        names = extract_listing_names(decode_listing(path))
    else:
        raise ValueError("Wybierz katalog lub plik .txt z nazwami filmów.")
    queries = unique_movie_queries(names)
    if not queries:
        raise ValueError("Nie znaleziono plików wideo ani nazw katalogów filmowych. W TXT umieść jedną nazwę filmu lub katalogu w wierszu; rozszerzenie .mkv lub .mp4 nie jest wymagane.")
    return queries


def suggested_report_path(path: Path) -> Path:
    return path.parent / (path.name + ".html") if path.is_dir() else path.with_suffix(".html")

"""Test gotowego pakietu bez sieci i bez otwierania okna na pulpicie."""

import json
import os
import sys
import tempfile
from pathlib import Path

from . import __version__


def run_self_test(output: Path) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {"version": __version__, "ok": False, "frozen": bool(getattr(sys, "frozen", False))}
    window = None
    try:
        from PySide6.QtWidgets import QApplication
        from .app import MainWindow
        from .cache import MovieCache
        from .inputs import load_queries
        from .models import MovieData, MovieResult
        from .report import write_report

        application = QApplication.instance() or QApplication([])
        application.setApplicationName("MovieCheck")
        application.setOrganizationName("MovieCheck")
        application.setApplicationVersion(__version__)
        window = MainWindow()
        if window.windowIcon().isNull():
            raise RuntimeError("W pakiecie brakuje ikony aplikacji.")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "lista.txt"
            source.write_text("Test.Movie.2026.1080p-WEB\n", encoding="utf-8")
            query = load_queries(source)[0]
            if query.title != "Test Movie" or query.year != 2026:
                raise RuntimeError("Nieprawidłowe rozpoznawanie wejścia w pakiecie.")
            cache = MovieCache(root / "cache.sqlite3")
            try:
                cache.put("test", {"value": 1})
                if cache.get("test") != {"value": 1}:
                    raise RuntimeError("SQLite nie działa w pakiecie.")
            finally:
                cache.close()
            movie = MovieData("Test Movie", "https://www.imdb.com/title/tt1", "IMDb", rating="7.1", description="Opis testowy.")
            report = output.with_suffix(".html")
            write_report(report, source, [MovieResult(query, [movie])])
            html = report.read_text(encoding="utf-8")
            if "Opis testowy." not in html or f"MovieCheck {__version__}" not in html:
                raise RuntimeError("Nieprawidłowy szablon raportu w pakiecie.")
        result.update(ok=True, icon=True, qt=True, sqlite=True, report=str(report), input=True)
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    finally:
        if window:
            window.close()
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1

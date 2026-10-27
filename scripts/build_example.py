"""Tworzy raport przykładowy z rzeczywistych danych; opcjonalnie zapisuje podgląd Qt."""

import argparse
import os
from pathlib import Path

from moviecheck.cache import MovieCache
from moviecheck.inputs import load_queries
from moviecheck.report import write_report
from moviecheck.service import MovieService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshot", action="store_true", help="Zapisz podgląd okna Qt bez otwierania okna na pulpicie")
    parser.add_argument("--input", type=Path, help="Osobna lista lub katalog do sprawdzenia")
    parser.add_argument("--limit", type=int, help="Maksymalna liczba filmów w próbie")
    arguments = parser.parse_args()
    if arguments.limit is not None and arguments.limit <= 0:
        parser.error("Limit musi być dodatni.")
    root = Path(__file__).resolve().parents[1]
    output_directory = root / "build"
    output_directory.mkdir(exist_ok=True)
    source = arguments.input.resolve() if arguments.input else root / "examples" / "lista.txt"
    cache = MovieCache(output_directory / "example.sqlite3")
    service = MovieService(cache)
    results = []
    try:
        for query in load_queries(source)[:arguments.limit]:
            result = service.lookup(query)
            results.append(result)
            ratings = ", ".join(f"{entry.source}: {entry.rating or 'brak oceny'}" for entry in result.entries)
            subscriptions = ", ".join(offer.provider_name for offer in result.vod.offers) or "brak potwierdzonych ofert"
            print(f"{query.title}: {result.status} | {ratings} | VOD: {subscriptions}", flush=True)
            for note in result.notes:
                print(f"  {note}", flush=True)
        report = output_directory / "lista.html"
        write_report(report, source, results)
        print(f"Raport: {report}", flush=True)
    finally:
        service.close()
        cache.close()
    if arguments.screenshot:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QFont, QFontDatabase
        from moviecheck.app import MainWindow

        application = QApplication([])
        # Wtyczka offscreen Qt na Windows może nie wykrywać fontów systemowych.
        if os.name == "nt":
            font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "segoeui.ttf"
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))
                application.setFont(QFont("Segoe UI", 10))
        window = MainWindow()
        window.load_source(source)
        window.results = window.results[:len(results)]
        window.table.setRowCount(len(results))
        for index, result in enumerate(results):
            window.receive_result(index, result)
        window.report_path = report
        window.set_busy(False)
        window.progress.setMaximum(len(results))
        window.progress.setValue(len(results))
        window.table.selectRow(0)
        window.status.setText(f"Raport przykładowy: {report}")
        window.show()
        application.processEvents()
        screenshot = output_directory / "app-preview.png"
        if not window.grab().save(str(screenshot)):
            raise RuntimeError("Nie udało się zapisać podglądu okna.")
        print(f"Podgląd: {screenshot}", flush=True)
        window.close()


if __name__ == "__main__":
    main()

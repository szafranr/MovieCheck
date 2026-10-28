"""Pomiar rzeczywistych serwisów; uruchamiaj jako python -m scripts.profile_search."""

import argparse
import json
from pathlib import Path

from PySide6.QtCore import Qt
from moviecheck.app import SearchWorker
from moviecheck.inputs import load_queries
from moviecheck.models import MovieQuery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--output", type=Path, default=Path("build/profile-parallel.json"))
    args = parser.parse_args()
    if args.limit < 1 or not 1 <= args.workers <= 16:
        parser.error("Limit musi być dodatni, pracownicy: 1–16.")
    queries = load_queries(args.input) if args.input else [MovieQuery(title + ".mkv", title, year)
        for title, year in (("Inception", 2010), ("Interstellar", 2014), ("The Matrix", 1999))]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    worker = SearchWorker([(index, query, "") for index, query in enumerate(queries[:args.limit])], args.output.with_suffix(".sqlite3"), True, workers=args.workers)
    results = []
    def receive(index, result):
        results.append({"index": index, "status": result.status, "sources": [movie.source for movie in result.entries]})
        print(f"Wynik {len(results)}: {result.status}", flush=True)
    worker.result_ready.connect(receive, Qt.ConnectionType.DirectConnection)
    worker.run()
    data = {"elapsed_seconds": round(worker.elapsed, 3), "workers": args.workers,
            "error": worker.error, "partial": worker.partial, "stages": worker.state.summary(), "results": results}
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2), flush=True)
    if worker.error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

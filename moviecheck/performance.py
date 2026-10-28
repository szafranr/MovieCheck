"""Wspólny stan serii, ograniczenie ruchu i pomiary czasu bez danych poufnych."""

import logging
import threading
import time
from contextlib import contextmanager


class BatchState:
    def __init__(self):
        self.ratings_lock = threading.Lock()
        self.ratings_failure = ""
        self.ratings_refreshed = False
        self.pages_unavailable = threading.Event()
        self.lock = threading.Lock()
        self.next_request = {}
        self.timings = {}

    def wait_for_request(self, host, cancelled):
        # Ograniczenie dotyczy całej serii, niezależnie od liczby pracowników.
        while not cancelled():
            with self.lock:
                now = time.monotonic()
                delay = self.next_request.get(host, 0) - now
                if delay <= 0:
                    self.next_request[host] = now + 0.2
                    return
            time.sleep(min(delay, 0.05))

    def record(self, name, elapsed):
        with self.lock:
            total, count = self.timings.get(name, (0.0, 0))
            self.timings[name] = (total + elapsed, count + 1)

    @contextmanager
    def measure(self, name):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, time.perf_counter() - start)

    def summary(self):
        with self.lock:
            return {name: {"seconds": round(total, 3), "count": count}
                    for name, (total, count) in sorted(self.timings.items())}

    def log(self, elapsed, workers):
        logging.getLogger("moviecheck.performance").info(
            "Czas serii %.3f s; pracownicy=%s; sumy czasu etapów (nakładają się): %s",
            elapsed, workers, self.summary())

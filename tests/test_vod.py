import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from bs4 import BeautifulSoup

from moviecheck.cache import MovieCache
from moviecheck.models import MovieData, MovieQuery, MovieResult, VodAvailability
from moviecheck.report import write_report
from moviecheck.vod import FilmwebVod, subscription_offers

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
PROVIDERS = [
    {"id": 1, "displayName": "Netflix", "path": "/1_2.$.svg", "abonaments": "3000", "countryCode": "PL"},
    {"id": 2, "displayName": "Apple TV Store", "path": "/2.$.svg", "countryCode": "PL"},
    {"id": 3, "displayName": "SkyShowtime (Prime Video)", "path": "/3.$.svg", "parent": 8, "countryCode": "PL"},
]


def offer(provider_id, payments=None, **fields):
    return {"vodProvider": provider_id, "status": 0, "link": f"https://example.com/movie/{provider_id}", "payments": payments, **fields}


class VodTests(unittest.TestCase):
    def test_extreme_filmweb_dates_do_not_use_windows_timestamp_conversion(self):
        for start, end in (("0001-01-01T00:00:00", "9999-12-31T00:00:00"),
                           ("1900-01-01T00:00:00", "9999-12-31T00:00:00+14:00"),
                           ("1960-01-01T00:00:00+00:00", "2255-01-01T00:00:00")):
            with self.subTest(start=start, end=end):
                results = subscription_offers([offer(1, start=start, end=end)], PROVIDERS, NOW)
                self.assertEqual([item.provider_name for item in results], ["Netflix"])

    def test_invalid_offer_date_does_not_discard_other_offers(self):
        rows = [offer(1, end="99999-12-31T00:00:00"), offer(3, [{"subscription": True}], end="9999-12-31T00:00:00")]
        self.assertEqual([item.provider_name for item in subscription_offers(rows, PROVIDERS, NOW)], ["SkyShowtime (Prime Video)"])

    def test_only_subscription_offers_and_no_provider_name_guessing(self):
        rows = [offer(1, [{"subscription": False, "rent": True}]), offer(2, [{"subscription": False, "buy": True}]), offer(3, [{"subscription": True, "rent": False, "buy": False}])]
        results = subscription_offers(rows, PROVIDERS, NOW)
        self.assertEqual([item.provider_name for item in results], ["SkyShowtime (Prime Video)"])
        self.assertTrue(results[0].additional_subscription)

    def test_subscription_without_per_film_payment_requires_explicit_platform_plan(self):
        results = subscription_offers([offer(1), offer(2)], PROVIDERS, NOW)
        self.assertEqual([item.provider_name for item in results], ["Netflix"])
        self.assertEqual(results[0].logo_url, "https://fwcdn.pl/vodp/1_2.1.svg")

    def test_mixed_payments_keep_subscription_and_deduplicate_platform(self):
        rows = [offer(1, [{"rent": True}, {"subscription": True}]), offer(1, [{"subscription": True}])]
        self.assertEqual(len(subscription_offers(rows, PROVIDERS, NOW)), 1)

    def test_unknown_or_free_platform_plan_is_not_a_confirmed_subscription(self):
        for plans in (None, "0", "unknown", [], True):
            with self.subTest(plans=plans):
                providers = [{"id": 1, "displayName": "Provider", "abonaments": plans, "countryCode": "PL"}]
                self.assertEqual(subscription_offers([offer(1)], providers, NOW), [])

    def test_free_rental_purchase_and_unknown_payment_types_are_excluded(self):
        for payment in ({"free": True}, {"buy": True}, {"rent": True}, {"accessType": 2}, {"subscription": "true"}, {"subscription": True, "rent": True}):
            with self.subTest(payment=payment):
                self.assertEqual(subscription_offers([offer(1, [payment])], PROVIDERS, NOW), [])

    def test_inactive_expired_future_and_non_polish_offers_are_excluded(self):
        rows = [offer(1, status=1), offer(1, end="2026-10-26T20:00:00+00:00"), offer(1, start="2026-10-28T20:00:00+00:00"), offer(1, start="bad date"), offer(99)]
        providers = PROVIDERS + [{"id": 99, "displayName": "Other country", "abonaments": "1000", "countryCode": "US"}]
        self.assertEqual(subscription_offers(rows, providers, NOW), [])

    def test_invalid_links_are_not_included(self):
        self.assertEqual(subscription_offers([offer(1, link="javascript:alert(1)")], PROVIDERS, NOW), [])

    def test_vod_cache_refreshes_offers_after_six_hours(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = MovieCache(Path(directory) / "cache.sqlite3")
            fetch = Mock(side_effect=[json.dumps(PROVIDERS), json.dumps([offer(1)]), json.dumps([])])
            vod = FilmwebVod(cache, fetch)
            try:
                url = "https://www.filmweb.pl/film/Film-2020-1"
                self.assertEqual(len(vod.lookup(url).offers), 1)
                self.assertEqual(len(vod.lookup(url).offers), 1)
                self.assertEqual(fetch.call_count, 2)
                key = "https://www.filmweb.pl/api/v1/vod/film/1/providers/list?countryCode=PL"
                cache.put(key, {"data": [offer(1)], "checked_at": time.time() - 7 * 3600})
                self.assertEqual(vod.lookup(url).offers, [])
                self.assertEqual(fetch.call_count, 3)
            finally:
                cache.close()

    def test_report_shows_two_independent_ratings_and_subscription_logos(self):
        with tempfile.TemporaryDirectory() as directory:
            result = MovieResult(MovieQuery("Film.mkv", "Film"), [MovieData("Film", "https://www.filmweb.pl/film/Film-2020-1", "Filmweb", rating="7.3"), MovieData("Film", "https://www.imdb.com/title/tt1", "IMDb", rating="8.1")])
            result.vod = VodAvailability(subscription_offers([offer(1), offer(2, [{"rent": True}]), offer(3, [{"subscription": True}])], PROVIDERS, NOW), "2026-10-27 12:00")
            path = Path(directory) / "report.html"
            write_report(path, Path("lista.txt"), [result])
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            self.assertEqual([item.get_text(strip=True) for item in soup.select(".badge")], ["Filmweb: 7.3 / 10", "IMDb: 8.1 / 10"])
            vod = soup.select_one(".vod")
            self.assertIn("Netflix", vod.get_text())
            self.assertNotIn("Apple TV Store", vod.get_text())
            self.assertIn("Dodatkowy abonament", vod.get_text())
            self.assertEqual(len(vod.select("img")), 2)
            self.assertIn("Polska", vod.get_text())

    def test_missing_imdb_rating_is_not_replaced_by_filmweb_score(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.html"
            result = MovieResult(MovieQuery("Film.mkv", "Film"), [MovieData("Film", "https://www.filmweb.pl/film/Film-2020-1", "Filmweb", rating="7.3")])
            write_report(path, Path("lista.txt"), [result])
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            self.assertEqual([item.get_text(strip=True) for item in soup.select(".badge")], ["Filmweb: 7.3 / 10", "IMDb: brak oceny"])
            self.assertIsNone(soup.select_one(".vod"))

import json
import re
import time
from datetime import datetime

from .models import VodAvailability, VodOffer
from .providers import ProviderError, image_url, validate_movie_url


def subscription_offers(offers: list, providers: list, now: datetime | None = None) -> list[VodOffer]:
    if not isinstance(offers, list) or not isinstance(providers, list):
        raise ProviderError("Nierozpoznany format ofert VOD Filmweb.")
    now = now or datetime.now().astimezone()
    provider_map = {str(provider["id"]): provider for provider in providers if isinstance(provider, dict) and "id" in provider}
    selected = {}
    for offer in offers:
        if not isinstance(offer, dict) or offer.get("status") != 0:
            continue
        provider = provider_map.get(str(offer.get("vodProvider")))
        if not provider or provider.get("countryCode") != "PL":
            continue
        try:
            start = datetime.fromisoformat(offer["start"]).astimezone() if offer.get("start") else None
            end = datetime.fromisoformat(offer["end"]).astimezone() if offer.get("end") else None
        except (ValueError, TypeError):
            continue
        if (start and start > now) or (end and end <= now):
            continue
        payments = offer.get("payments")
        if payments:
            if not isinstance(payments, list):
                continue
            subscribed = any(isinstance(payment, dict) and payment.get("subscription") is True
                             and payment.get("rent") is not True and payment.get("buy") is not True
                             and payment.get("free") is not True for payment in payments)
        else:
            # Tak Filmweb opisuje m.in. Netflix/HBO Max: brak osobnej ceny
            # filmu, ale jawnie zdefiniowany abonament w metadanych platformy.
            plans = provider.get("abonaments")
            subscribed = isinstance(plans, str) and bool(re.fullmatch(r"\d+(?:,\d+)*", plans)) and any(int(price) > 0 for price in plans.split(","))
        if not subscribed:
            continue
        name = str(provider.get("displayName") or "").strip()
        url = image_url(offer.get("link"))
        if not name or not url:
            continue
        path = provider.get("path")
        logo = image_url("https://fwcdn.pl/vodp" + path.replace("$", "1")) if isinstance(path, str) and path.startswith("/") else ""
        key = str(provider["id"])
        selected.setdefault(key, VodOffer(name, url, logo, bool(provider.get("parent"))))
    return sorted(selected.values(), key=lambda offer: offer.provider_name.casefold())


class FilmwebVod:
    def __init__(self, cache, fetch):
        self.cache = cache
        self.fetch = fetch

    def read_json(self, url: str, max_age: float):
        cached = self.cache.get(url)
        if cached and isinstance(cached, dict) and time.time() - cached.get("checked_at", 0) < max_age:
            return cached["data"], cached["checked_at"]
        try:
            data = json.loads(self.fetch(url))
        except ValueError as error:
            raise ProviderError("Nie udało się odczytać danych VOD Filmweb.") from error
        if not isinstance(data, list):
            raise ProviderError("Nierozpoznany format danych VOD Filmweb.")
        checked_at = time.time()
        self.cache.put(url, {"data": data, "checked_at": checked_at})
        return data, checked_at

    def lookup(self, movie_url: str) -> VodAvailability:
        movie_url = validate_movie_url(movie_url, "Filmweb")
        movie_id = re.search(r"-(\d+)$", movie_url).group(1)
        providers, _ = self.read_json("https://www.filmweb.pl/api/v1/vod/providers/list?countryCode=PL", 7 * 86400)
        offers, checked_at = self.read_json(f"https://www.filmweb.pl/api/v1/vod/film/{movie_id}/providers/list?countryCode=PL", 6 * 3600)
        return VodAvailability(subscription_offers(offers, providers), datetime.fromtimestamp(checked_at).astimezone().strftime("%Y-%m-%d %H:%M"))

"""Place search via Photon (OpenStreetMap data, no API key, built for autocomplete)."""

import hashlib

from django.conf import settings
from django.core.cache import cache

from trips.services.http import get_json


def search_places(query: str, limit: int = 6) -> list[dict]:
    query = query.strip()
    cache_key = f"geocode:{hashlib.sha1(query.lower().encode()).hexdigest()}:{limit}"
    if (cached := cache.get(cache_key)) is not None:
        return cached

    data = get_json(
        settings.PHOTON_URL,
        params={"q": query, "limit": limit, "lang": "en", "lat": 39.8, "lon": -98.6},
    )
    places = []
    for feature in data.get("features", []):
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        parts = [props.get("name"), props.get("city"), props.get("state"), props.get("country")]
        label = ", ".join(dict.fromkeys(p for p in parts if p))
        places.append({"label": label, "lat": lat, "lon": lon})
    cache.set(cache_key, places, 24 * 3600)
    return places

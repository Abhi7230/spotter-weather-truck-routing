"""Shared HTTP session for third-party APIs."""

import requests
from django.conf import settings


class UpstreamError(Exception):
    """A third-party API (routing, weather, geocoding) failed or returned bad data."""


_session = requests.Session()


def get_json(url: str, params: dict | None = None) -> dict | list:
    try:
        response = _session.get(
            url,
            params=params,
            headers={"User-Agent": settings.HTTP_USER_AGENT},
            timeout=settings.HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpstreamError(f"Request to {url.split('?')[0]} failed: {exc}") from exc

"""Shared HTTP session for third-party APIs, with retries for transient failures."""

import logging

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class UpstreamError(Exception):
    """A third-party API (routing, weather, geocoding) failed or returned bad data.

    The message is shown to the user, so keep it readable.
    """


_session = requests.Session()
_session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
    ),
)


def get_json(url: str, params: dict | None = None, service: str = "An external service"):
    try:
        response = _session.get(
            url,
            params=params,
            headers={"User-Agent": settings.HTTP_USER_AGENT},
            timeout=settings.HTTP_TIMEOUT_SECONDS,
        )
        if 400 <= response.status_code < 500 and response.status_code != 429:
            # A client error means retrying won't help; pass the API's reason on.
            body = _json_or_empty(response)
            reason = body.get("message") or body.get("reason") or f"HTTP {response.status_code}"
            raise UpstreamError(f"{service} rejected the request: {reason}")
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("%s request failed: %s", service, exc)
        raise UpstreamError(f"{service} is not responding right now. Please try again.") from exc


def _json_or_empty(response: requests.Response) -> dict:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}

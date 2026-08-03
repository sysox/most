"""Small standard-library JSON HTTP transport for provider adapters."""

from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .openai_compatible import HTTPResponse


def urllib_json_transport(url: str, headers: Mapping[str, str], payload: dict[str, object], timeout: float = 60.0) -> HTTPResponse:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
            if not isinstance(body, dict):
                raise TypeError("provider response must be a JSON object")
            return HTTPResponse(response.status, body)
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {"error": str(exc)}
        return HTTPResponse(exc.code, body if isinstance(body, dict) else {"error": body})
    except URLError as exc:
        raise ConnectionError(f"provider connection failed: {exc.reason}") from exc

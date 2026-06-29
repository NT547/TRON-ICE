from __future__ import annotations

import logging
import time
from typing import Any

import requests

from config import (
    MAX_RETRIES,
    RATE_LIMIT_DEFAULT_SLEEP_SEC,
    RECENT_SHIFTS_URL,
    REQUEST_LIMIT,
    REQUEST_TIMEOUT_SEC,
    RETRY_BASE_DELAY_SEC,
    RETRY_MAX_DELAY_SEC,
)

logger = logging.getLogger(__name__)


class SideShiftClient:
    def __init__(
        self,
        base_url: str = RECENT_SHIFTS_URL,
        limit: int = REQUEST_LIMIT,
        timeout: float = REQUEST_TIMEOUT_SEC,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url
        self.limit = max(1, min(limit, 100))
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")

    def fetch_recent_shifts(self) -> list[dict[str, Any]]:
        params = {"limit": self.limit}
        last_error: Exception | None = None
        last_status: int | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.session.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout,
                )

                if response.status_code == 429:
                    last_status = 429
                    retry_after = _parse_retry_after(response)
                    logger.warning(
                        "Rate limited (429). Sleeping %ss before retry (attempt %s/%s).",
                        retry_after,
                        attempt,
                        MAX_RETRIES,
                    )
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                data = response.json()

                if not isinstance(data, list):
                    raise ValueError(f"Expected list response, got {type(data).__name__}")

                return data

            except requests.RequestException as exc:
                last_error = exc
                delay = min(
                    RETRY_BASE_DELAY_SEC * (2 ** (attempt - 1)),
                    RETRY_MAX_DELAY_SEC,
                )
                logger.error(
                    "API request failed (attempt %s/%s): %s. Retrying in %ss.",
                    attempt,
                    MAX_RETRIES,
                    exc,
                    delay,
                )
                time.sleep(delay)

        if last_status == 429:
            raise RuntimeError(
                f"Rate limited after {MAX_RETRIES} attempts"
            ) from last_error
        raise RuntimeError(
            f"Failed to fetch recent shifts after {MAX_RETRIES} attempts"
        ) from last_error


def _parse_retry_after(response: requests.Response) -> int:
    header = response.headers.get("Retry-After")
    if header is not None:
        try:
            return max(int(header), 1)
        except ValueError:
            pass
    return RATE_LIMIT_DEFAULT_SLEEP_SEC

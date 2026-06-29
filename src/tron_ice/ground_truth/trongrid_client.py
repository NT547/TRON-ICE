from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests


logger = logging.getLogger(__name__)


class TronGridClient:
    """
    Minimal TronGrid client for fetching TRX/TRC20 transfers by address within a time window.
    Uses TRONGRID_API_KEY from environment (same convention as src/utils/configs.py).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.trongrid.io/v1/accounts",
        timeout_sec: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.api_key = api_key or os.getenv("TRONGRID_API_KEY")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"TRON-PRO-API-KEY": self.api_key})
        self.session.headers.setdefault("Accept", "application/json")

    def fetch_trx_transfers(
        self, address: str, min_ts: int, max_ts: int, limit: int = 200
    ) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{address}/transactions"
        return self._fetch_paged(url, min_ts, max_ts, limit=limit)

    def fetch_trc20_transfers(
        self,
        address: str,
        min_ts: int,
        max_ts: int,
        limit: int = 200,
        contract_address: str | None = None,
    ) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{address}/transactions/trc20"
        params_extra: dict[str, Any] = {}
        if contract_address:
            params_extra["contract_address"] = contract_address
        return self._fetch_paged(url, min_ts, max_ts, limit=limit, params_extra=params_extra)

    def _fetch_paged(
        self,
        url: str,
        min_ts: int,
        max_ts: int,
        limit: int,
        params_extra: dict[str, Any] | None = None,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "limit": min(max(int(limit), 1), 200),
            "order_by": "block_timestamp,asc",
            "only_confirmed": "true",
            "min_timestamp": int(min_ts),
            "max_timestamp": int(max_ts),
        }
        if params_extra:
            params.update(params_extra)

        all_rows: list[dict[str, Any]] = []
        fingerprint: str | None = None

        for page in range(1, max_pages + 1):
            if fingerprint:
                params["fingerprint"] = fingerprint
            resp = self._request_with_retry(url, params=params)
            data = resp.json()
            rows = data.get("data") or []
            if not rows:
                break
            all_rows.extend(rows)
            fingerprint = (data.get("meta") or {}).get("fingerprint")
            if not fingerprint:
                break
            time.sleep(0.25)

        return all_rows

    def _request_with_retry(self, url: str, params: dict[str, Any]) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(1, 6):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout_sec)
                if resp.status_code == 429:
                    retry_after = _parse_retry_after(resp) or min(60 * attempt, 180)
                    logger.warning("TronGrid 429 rate limit; sleep %ss", retry_after)
                    time.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                last_exc = exc
                sleep_s = min(2**attempt, 30)
                logger.warning("TronGrid request failed (attempt %s): %s; sleep %ss", attempt, exc, sleep_s)
                time.sleep(sleep_s)
        raise RuntimeError("TronGrid request failed after retries") from last_exc


def _parse_retry_after(resp: requests.Response) -> int | None:
    ra = resp.headers.get("Retry-After")
    if not ra:
        return None
    try:
        return max(int(ra), 1)
    except ValueError:
        return None


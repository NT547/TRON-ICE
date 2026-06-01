from __future__ import annotations

import logging
import time
from typing import Any

import requests

from config import (
    CHANGENOW_API_KEY,
    CURRENCIES_V2_URL,
    MAX_RETRIES,
    RATE_LIMIT_DEFAULT_SLEEP_SEC,
    REQUEST_LIMIT,
    REQUEST_TIMEOUT_SEC,
    RETRY_BASE_DELAY_SEC,
    RETRY_MAX_DELAY_SEC,
    TRANSACTIONS_V1_URL,
)

logger = logging.getLogger(__name__)

_NON_RETRYABLE = frozenset({401, 403, 404, 405})


class ChangeNowApiError(RuntimeError):
    """ChangeNOW API rejected the request (auth, permissions, or endpoint)."""


class ChangeNowClient:
    """Partner API client: lists transactions created under your API key."""

    def __init__(
        self,
        api_key: str | None = None,
        limit: int = REQUEST_LIMIT,
        timeout: float = REQUEST_TIMEOUT_SEC,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = (api_key or CHANGENOW_API_KEY).strip()
        if not self.api_key:
            raise ValueError(
                "CHANGENOW_API_KEY is missing. Add it to .env (ChangeNOW for Business / Partner)."
            )
        self.limit = max(1, min(limit, 100))
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("Accept", "application/json")
        self.session.headers["x-changenow-api-key"] = self.api_key

    def check_connectivity(self) -> dict[str, Any]:
        """
        Quick health check: public key works for v2 metadata, list endpoint permissions.
        Does not log the API key.
        """
        out: dict[str, Any] = {"api_key_len": len(self.api_key), "public_key_ok": False, "list_transactions_ok": False}
        try:
            r = self.session.get(CURRENCIES_V2_URL, timeout=self.timeout)
            out["public_key_ok"] = r.status_code == 200
            out["currencies_status"] = r.status_code
        except requests.RequestException as exc:
            out["currencies_error"] = str(exc)
            return out

        url = TRANSACTIONS_V1_URL.format(api_key=self.api_key)
        try:
            r = self.session.get(url, params={"limit": 1}, timeout=self.timeout)
            out["list_status"] = r.status_code
            if r.status_code == 200:
                out["list_transactions_ok"] = True
            elif r.headers.get("content-type", "").startswith("application/json"):
                body = r.json()
                out["list_error"] = body.get("error")
                out["list_message"] = body.get("message")
        except requests.RequestException as exc:
            out["list_error"] = str(exc)
        return out

    def fetch_recent_transactions(
        self,
        *,
        status: str | None = "finished",
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        last_status: int | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._fetch_v1_list(status=status, offset=offset)
            except ChangeNowApiError:
                raise
            except requests.RequestException as exc:
                last_error = exc
                resp = getattr(exc, "response", None)
                if resp is not None:
                    last_status = resp.status_code
                    if resp.status_code in _NON_RETRYABLE:
                        raise _http_error(resp) from exc
                    if resp.status_code == 429:
                        retry_after = _parse_retry_after(resp)
                        logger.warning("Rate limited; sleep %ss", retry_after)
                        time.sleep(retry_after)
                        continue
                delay = min(RETRY_BASE_DELAY_SEC * (2 ** (attempt - 1)), RETRY_MAX_DELAY_SEC)
                logger.error("Request failed (%s/%s): %s; sleep %ss", attempt, MAX_RETRIES, exc, delay)
                time.sleep(delay)

        if last_status == 429:
            raise RuntimeError("Rate limited after retries") from last_error
        raise RuntimeError("Failed to fetch ChangeNOW transactions") from last_error

    def _fetch_v1_list(self, *, status: str | None, offset: int) -> list[dict[str, Any]]:
        """GET /v1/transactions/{api_key} — partner transaction list (standard flow)."""
        url = TRANSACTIONS_V1_URL.format(api_key=self.api_key)
        params: dict[str, Any] = {"limit": self.limit, "offset": offset}
        if status:
            params["status"] = status

        response = self.session.get(url, params=params, timeout=self.timeout)
        if not response.ok:
            raise _http_error(response)
        return _normalize_list_response(response.json())


def _http_error(response: requests.Response) -> ChangeNowApiError:
    status = response.status_code
    detail = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = f"{body.get('error', '')}: {body.get('message', '')}".strip(": ")
    except ValueError:
        detail = (response.text or "")[:200]

    if status == 401 and "private key" in detail.lower():
        return ChangeNowApiError(
            "ChangeNOW rejected listing transactions with your public API key "
            f"({detail or '401 Unauthorized'}). "
            "As of 2026, GET /v1/transactions/{api_key} requires a **private** partner key "
            "(issued via GPG for v2/exchanges), which cannot be used for this crawler. "
            "Contact api@changenow.io or use on-chain hot-wallet scraping for ChangeNOW ICE data."
        )
    if status == 401:
        return ChangeNowApiError(
            f"ChangeNOW API key unauthorized ({detail or '401'}). "
            "Verify CHANGENOW_API_KEY in .env (no spaces) from ChangeNOW Business → Profile."
        )
    return ChangeNowApiError(f"ChangeNOW HTTP {status}: {detail or response.reason}")


def _normalize_list_response(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("transactions", "data", "result", "items"):
            inner = data.get(key)
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
    raise ValueError(f"Unexpected ChangeNOW response shape: {type(data).__name__}")


def _parse_retry_after(response: requests.Response) -> int:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return max(int(header), 1)
        except ValueError:
            pass
    return RATE_LIMIT_DEFAULT_SLEEP_SEC

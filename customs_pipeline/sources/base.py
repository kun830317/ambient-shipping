"""Shared HTTP helpers for source fetchers."""

import time

import requests

USER_AGENT = "ambient-shipping-customs-pipeline/0.1 (research; github.com/kun830317/ambient-shipping)"


def get(url, params=None, retries=3, backoff=2.0, timeout=60, **kwargs):
    """GET with polite retry/backoff. Raises on final failure."""
    headers = kwargs.pop("headers", {})
    headers.setdefault("User-Agent", USER_AGENT)
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers,
                                timeout=timeout, **kwargs)
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError("HTTP %d" % resp.status_code,
                                         response=resp)
            resp.raise_for_status()
            return resp
        except requests.RequestException as err:
            last_err = err
            status = getattr(getattr(err, "response", None), "status_code", None)
            # Client errors other than rate-limiting won't fix themselves.
            if status is not None and 400 <= status < 500 and status != 429:
                raise
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
    raise last_err


def to_float(value):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None

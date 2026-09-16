"""Self-hosted geocoding boundary. Never sends reports to the public Nominatim service."""

import hashlib
import json
import threading
import time
from collections import OrderedDict
from difflib import SequenceMatcher
from typing import Literal, Protocol
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .ai import folded


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    provider_id: str = Field(max_length=120)
    display_name: str = Field(max_length=1500)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    precision: Literal["building", "street", "area", "unknown"] = "unknown"
    match_score: float = Field(default=0, ge=0, le=1)
    provenance: str = Field(max_length=100)


class Geocoder(Protocol):
    def candidates(self, tenant_id: str, address: str, language: str) -> list[Candidate]: ...


class GeocoderUnavailable(RuntimeError):
    pass


class NominatimSelfHosted:
    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
        requests_per_second: float = 5.0,
        max_retries: int = 2,
        breaker_failures: int = 3,
        breaker_cooldown_seconds: float = 30.0,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        parsed = urlparse(base_url)
        host = (parsed.hostname or "").rstrip(".").lower()
        if host == "nominatim.openstreetmap.org" or host.endswith(".openstreetmap.org"):
            raise ValueError("Public OSM geocoder prohibited for automated disaster reports")
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Explicit administrator-configured geocoder origin required")
        if parsed.scheme == "http" and host not in {"127.0.0.1", "localhost", "geocoder"}:
            raise ValueError("Remote geocoder requires HTTPS")
        if not 0.1 <= requests_per_second <= 50:
            raise ValueError("requests_per_second must be 0.1..50")
        if not 0 <= max_retries <= 3 or not 1 <= breaker_failures <= 10:
            raise ValueError("invalid retry or circuit-breaker bounds")
        if not 1 <= breaker_cooldown_seconds <= 300:
            raise ValueError("invalid circuit-breaker cooldown")
        self.url = base_url.rstrip("/") + "/search"
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(3.0), follow_redirects=False, trust_env=False
        )
        self.lock = threading.Lock()
        self.cache: OrderedDict[str, tuple[float, list[Candidate]]] = OrderedDict()
        self.min_interval = 1 / requests_per_second
        self.max_retries = max_retries
        self.breaker_failures = breaker_failures
        self.breaker_cooldown_seconds = breaker_cooldown_seconds
        self.clock = clock
        self.sleep = sleep
        self.last_request_at: float | None = None
        self.consecutive_failures = 0
        self.breaker_opened_at: float | None = None

    def _before_request(self) -> None:
        with self.lock:
            now = self.clock()
            if self.breaker_opened_at is not None:
                if now - self.breaker_opened_at < self.breaker_cooldown_seconds:
                    raise GeocoderUnavailable("GEOCODER_CIRCUIT_OPEN")
                self.breaker_opened_at = None
                self.consecutive_failures = 0
            wait = (
                max(0.0, self.min_interval - (now - self.last_request_at))
                if self.last_request_at is not None
                else 0.0
            )
        if wait:
            self.sleep(wait)
        with self.lock:
            self.last_request_at = self.clock()

    def _record_result(self, success: bool) -> None:
        with self.lock:
            if success:
                self.consecutive_failures = 0
                self.breaker_opened_at = None
                return
            self.consecutive_failures += 1
            if self.consecutive_failures >= self.breaker_failures:
                self.breaker_opened_at = self.clock()

    def _request(self, address: str, language: str) -> list[dict]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                self._before_request()
                with self.client.stream(
                    "GET",
                    self.url,
                    params={
                        "q": address,
                        "format": "jsonv2",
                        "addressdetails": 1,
                        "limit": 5,
                        "accept-language": "en" if language == "und" else language,
                    },
                    headers={"User-Agent": "Komsu-self-hosted-geocoder/0.2"},
                ) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            "retryable geocoder response",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    if "application/json" not in response.headers.get("content-type", ""):
                        raise ValueError("provider did not return JSON")
                    buffer = bytearray()
                    for chunk in response.iter_bytes():
                        buffer.extend(chunk)
                        if len(buffer) > 65536:
                            raise ValueError("provider response too large")
                rows = json.loads(buffer)
                if not isinstance(rows, list) or len(rows) > 5:
                    raise ValueError("invalid provider response")
                self._record_result(True)
                return rows
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self.sleep(0.1 * (2**attempt))
        self._record_result(False)
        raise GeocoderUnavailable("GEOCODER_UNAVAILABLE") from last_error

    def candidates(self, tenant_id: str, address: str, language: str) -> list[Candidate]:
        if not address.strip() or len(address) > 1000 or language not in {"tr", "el", "en", "und"}:
            return []
        key = hashlib.sha256(f"{tenant_id}|{language}|{address}".encode()).hexdigest()
        now = self.clock()
        with self.lock:
            cached = self.cache.get(key)
            if cached and now - cached[0] < 3600:
                return [c.model_copy() for c in cached[1]]
        try:
            rows = self._request(address, language)
            result = []
            for row in rows:
                kind = row.get("addresstype", "")
                precision = (
                    "building"
                    if kind in {"building", "house"}
                    else "street"
                    if kind in {"road", "street"}
                    else "area"
                )
                result.append(
                    Candidate(
                        provider_id=str(row["place_id"]),
                        display_name=row["display_name"],
                        lat=row["lat"],
                        lon=row["lon"],
                        precision=precision,
                        match_score=SequenceMatcher(
                            None, folded(address), folded(row["display_name"])
                        ).ratio(),
                        provenance="self-hosted-nominatim:contract-v1",
                    )
                )
            result.sort(key=lambda c: c.match_score, reverse=True)
        except (KeyError, ValueError, TypeError) as exc:
            self._record_result(False)
            raise GeocoderUnavailable("GEOCODER_UNAVAILABLE") from exc
        with self.lock:
            self.cache[key] = (now, result)
            self.cache.move_to_end(key)
            while len(self.cache) > 1000:
                self.cache.popitem(last=False)
        return [c.model_copy() for c in result]


def location_annotation(candidates: list[Candidate]) -> dict:
    # Even one high-scoring candidate is a proposal, not a confirmed dispatch coordinate.
    ranked = sorted(candidates, key=lambda c: c.match_score, reverse=True)
    ambiguous = (
        not ranked
        or ranked[0].precision != "building"
        or ranked[0].match_score < 0.85
        or (len(ranked) > 1 and ranked[0].match_score - ranked[1].match_score < 0.15)
    )
    return {
        "location_candidates": [c.model_dump() for c in ranked],
        "location_status": "AMBIGUOUS_LOCATION" if ambiguous else "CANDIDATE_REQUIRES_REVIEW",
        "location": {"lat": None, "lon": None, "confidence": 0.0},
        "human_review_required": True,
    }

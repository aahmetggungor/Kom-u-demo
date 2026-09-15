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
    def __init__(self, base_url: str, *, client: httpx.Client | None = None):
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
        self.url = base_url.rstrip("/") + "/search"
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(3.0), follow_redirects=False, trust_env=False
        )
        self.lock = threading.Lock()
        self.cache: OrderedDict[str, tuple[float, list[Candidate]]] = OrderedDict()

    def candidates(self, tenant_id: str, address: str, language: str) -> list[Candidate]:
        if not address.strip() or len(address) > 1000 or language not in {"tr", "el", "en", "und"}:
            return []
        key = hashlib.sha256(f"{tenant_id}|{language}|{address}".encode()).hexdigest()
        now = time.monotonic()
        with self.lock:
            cached = self.cache.get(key)
            if cached and now - cached[0] < 3600:
                return [c.model_copy() for c in cached[1]]
        try:
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
                headers={"User-Agent": "Komsu-self-hosted-geocoder/0.1"},
            ) as response:
                response.raise_for_status()
                buffer = bytearray()
                for chunk in response.iter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) > 65536:
                        raise ValueError("provider response too large")
            rows = json.loads(buffer)
            if not isinstance(rows, list) or len(rows) > 5:
                raise ValueError("invalid provider response")
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
                        provenance="self-hosted-nominatim",
                    )
                )
            result.sort(key=lambda c: c.match_score, reverse=True)
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
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

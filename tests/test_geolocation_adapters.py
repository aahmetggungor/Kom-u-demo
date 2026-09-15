import hashlib
import hmac
from datetime import UTC, datetime

import httpx
import pytest
from komsu.adapters import ChannelAdapter, UpstreamMessage, verify_webhook_signature
from komsu.geolocation import (
    Candidate,
    GeocoderUnavailable,
    NominatimSelfHosted,
    location_annotation,
)
from komsu.schemas import Source


def test_public_geocoder_disabled():
    for uri in [
        "https://nominatim.openstreetmap.org",
        "https://nominatim.openstreetmap.org.",
        "http://remote.example",
        "https://user:pass@geo.example",
    ]:
        with pytest.raises(ValueError):
            NominatimSelfHosted(uri)


def test_candidates_are_never_automatic_coordinates():
    a = Candidate(
        provider_id="1",
        display_name="Synthetic building",
        lat=38,
        lon=27,
        precision="building",
        match_score=0.95,
        provenance="fixture",
    )
    result = location_annotation([a])
    assert (
        result["location_status"] == "CANDIDATE_REQUIRES_REVIEW"
        and result["location"]["lat"] is None
    )
    assert (
        location_annotation([a, a.model_copy(update={"provider_id": "2", "match_score": 0.90})])[
            "location_status"
        ]
        == "AMBIGUOUS_LOCATION"
    )
    assert (
        location_annotation([a.model_copy(update={"precision": "area"})])["location_status"]
        == "AMBIGUOUS_LOCATION"
    )


def test_provider_validation_cache_and_failure():
    calls = []

    def upstream(request):
        calls.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "place_id": 1,
                    "display_name": "Synthetic street 1",
                    "lat": "38",
                    "lon": "27",
                    "addresstype": "house",
                }
            ],
        )

    provider = NominatimSelfHosted(
        "https://geo.example", client=httpx.Client(transport=httpx.MockTransport(upstream))
    )
    assert len(provider.candidates("tenant", "Synthetic street 1", "tr")) == 1
    provider.candidates("tenant", "Synthetic street 1", "tr")
    assert len(calls) == 1
    provider.candidates("other", "Synthetic street 1", "tr")
    assert len(calls) == 2
    broken = NominatimSelfHosted(
        "https://geo.example",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json=[{"place_id": 1, "display_name": "bad", "lat": 999, "lon": 27}]
                )
            )
        ),
    )
    with pytest.raises(GeocoderUnavailable):
        broken.candidates("tenant", "address", "en")


def test_adapter_replay_identity_and_signature():
    adapter = ChannelAdapter("registered-sms-gateway", Source.sms)
    message = UpstreamMessage(
        external_id="provider-123",
        text="Synthetic report",
        received_at=datetime.now(UTC),
        language="en",
    )
    assert adapter.convert(message).client_id == adapter.convert(message).client_id
    secret = b"x" * 32
    body = b"synthetic"
    timestamp = 1000
    signature = hmac.new(secret, b"1000." + body, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(secret, body, timestamp, signature, 1100)
    assert not verify_webhook_signature(secret, body, timestamp, signature, 1500)
    assert not verify_webhook_signature(secret, body + b"modified", timestamp, signature, 1100)

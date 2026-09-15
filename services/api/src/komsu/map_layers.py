"""Bounded local GIS import. No URL fetching, executable properties or remote assets."""

import hashlib
import json
import math
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .schemas import StrictModel


class LayerIn(StrictModel):
    kind: Literal["hospital", "assembly", "shelter", "closed_road"]
    name: str = Field(min_length=1, max_length=160)
    provenance: str = Field(min_length=3, max_length=500)
    dataset_version: str = Field(min_length=1, max_length=120)
    license_name: str = Field(min_length=2, max_length=160)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_updated_at: datetime
    stale_after_days: int = Field(ge=1, le=3650)
    geojson: dict

    @field_validator("name", "provenance")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("nonblank source and name required")
        return value

    @field_validator("geojson")
    @classmethod
    def bounded_collection(cls, value):
        if set(value) != {"type", "features"} or value["type"] != "FeatureCollection":
            raise ValueError("FeatureCollection required")
        features = value["features"]
        if not isinstance(features, list) or not 1 <= len(features) <= 200:
            raise ValueError("1 to 200 features required")
        points = 0
        counts: dict[str, int] = {}

        def point(position):
            nonlocal points
            points += 1
            if points > 5000 or not isinstance(position, list) or len(position) != 2:
                raise ValueError("bounded 2D coordinates required")
            if any(type(n) not in (int, float) or not math.isfinite(n) for n in position):
                raise ValueError("finite numeric coordinates required")
            if abs(position[0]) > 180 or abs(position[1]) > 90:
                raise ValueError("WGS84 longitude/latitude required")

        for feature in features:
            if (
                not isinstance(feature, dict)
                or set(feature) != {"type", "geometry", "properties"}
                or feature["type"] != "Feature"
            ):
                raise ValueError("strict GeoJSON feature required")
            properties = feature["properties"]
            if not isinstance(properties, dict) or set(properties) - {"name"}:
                raise ValueError("only plain name property allowed")
            if "name" in properties and (
                not isinstance(properties["name"], str) or len(properties["name"]) > 160
            ):
                raise ValueError("bounded plain name required")
            geometry = feature["geometry"]
            if not isinstance(geometry, dict) or set(geometry) != {"type", "coordinates"}:
                raise ValueError("strict geometry required")
            coordinates = geometry["coordinates"]
            kind = geometry["type"]
            counts[kind] = counts.get(kind, 0) + 1
            if kind == "Point":
                point(coordinates)
            elif kind in {"LineString", "MultiPoint"}:
                if not isinstance(coordinates, list) or not 2 <= len(coordinates) <= 1000:
                    raise ValueError("bounded line or multipoint required")
                for position in coordinates:
                    point(position)
            elif kind == "MultiLineString":
                if not isinstance(coordinates, list) or not 1 <= len(coordinates) <= 100:
                    raise ValueError("bounded multiline required")
                for line in coordinates:
                    if not isinstance(line, list) or not 2 <= len(line) <= 1000:
                        raise ValueError("bounded multiline member required")
                    for position in line:
                        point(position)
            elif kind in {"Polygon", "MultiPolygon"}:
                polygons = [coordinates] if kind == "Polygon" else coordinates
                if not isinstance(polygons, list) or not 1 <= len(polygons) <= 50:
                    raise ValueError("bounded polygon collection required")
                for polygon in polygons:
                    if not isinstance(polygon, list) or not 1 <= len(polygon) <= 50:
                        raise ValueError("bounded polygon rings required")
                    for ring in polygon:
                        if not isinstance(ring, list) or not 4 <= len(ring) <= 1000:
                            raise ValueError("bounded polygon ring required")
                        if ring[0] != ring[-1]:
                            raise ValueError("polygon rings must be closed")
                        for position in ring:
                            point(position)
            else:
                raise ValueError("unsupported geometry")
        return value

    @model_validator(mode="after")
    def metadata_and_checksum(self):
        if self.source_updated_at.tzinfo is None:
            raise ValueError("source_updated_at must include timezone")
        self.source_updated_at = self.source_updated_at.astimezone(UTC)
        if self.source_updated_at > datetime.now(UTC):
            raise ValueError("source_updated_at cannot be in the future")
        actual = hashlib.sha256(
            json.dumps(
                self.geojson, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
        if actual != self.content_sha256:
            raise ValueError("content_sha256 does not match canonical GeoJSON")
        geometry_types = {feature["geometry"]["type"] for feature in self.geojson["features"]}
        allowed = (
            {"LineString", "MultiLineString"}
            if self.kind == "closed_road"
            else {"Point", "MultiPoint", "Polygon", "MultiPolygon"}
        )
        if not geometry_types <= allowed:
            raise ValueError("geometry is incompatible with layer kind")
        return self


def canonical_geojson_sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

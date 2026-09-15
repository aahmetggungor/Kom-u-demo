"""Bounded local GIS import. No URL fetching, executable properties or remote assets."""

import math
from typing import Literal

from pydantic import Field, field_validator

from .schemas import StrictModel


class LayerIn(StrictModel):
    kind: Literal["hospital", "assembly", "shelter", "closed_road"]
    name: str = Field(min_length=1, max_length=160)
    provenance: str = Field(min_length=3, max_length=500)
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

        def point(position):
            nonlocal points
            points += 1
            if points > 1000 or not isinstance(position, list) or len(position) != 2:
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
            if geometry["type"] == "Point":
                point(coordinates)
            elif geometry["type"] == "LineString":
                if not isinstance(coordinates, list) or not 2 <= len(coordinates) <= 1000:
                    raise ValueError("bounded line required")
                for position in coordinates:
                    point(position)
            else:
                raise ValueError("only Point and LineString supported in initial import")
        return value

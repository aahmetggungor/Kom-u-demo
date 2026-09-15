"""Verified local MapLibre style package boundary; no runtime downloads."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse


class MapPackageUnavailable(RuntimeError):
    pass


def _remote_urls(style: dict) -> list[str]:
    values = []
    for key in ("glyphs", "sprite"):
        if isinstance(style.get(key), str):
            values.append(style[key])
    for source in style.get("sources", {}).values():
        if isinstance(source, dict):
            if isinstance(source.get("url"), str):
                values.append(source["url"])
            values.extend(value for value in source.get("tiles", []) if isinstance(value, str))
    return values


def load_map_package(manifest_path: str | Path) -> dict:
    try:
        manifest_file = Path(manifest_path).resolve()
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        required = {
            "enabled",
            "package_version",
            "updated_at",
            "stale_after_days",
            "license_name",
            "attribution",
            "style_file",
            "style_sha256",
            "allowed_origins",
        }
        if set(manifest) != required or not isinstance(manifest["enabled"], bool):
            raise ValueError("invalid manifest fields")
        updated = datetime.fromisoformat(manifest["updated_at"])
        if updated.tzinfo is None or updated > datetime.now(UTC):
            raise ValueError("invalid package update time")
        stale_days = manifest["stale_after_days"]
        if type(stale_days) is not int or not 1 <= stale_days <= 3650:
            raise ValueError("invalid staleness bound")
        for key, limit in (("package_version", 120), ("license_name", 160), ("attribution", 500)):
            if (
                not isinstance(manifest[key], str)
                or not manifest[key].strip()
                or len(manifest[key]) > limit
            ):
                raise ValueError("invalid package metadata")
        if not isinstance(manifest["style_file"], str) or not manifest["style_file"].strip():
            raise ValueError("invalid style filename")
        if not isinstance(manifest["style_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", manifest["style_sha256"]
        ):
            raise ValueError("invalid style checksum")
        origins = manifest["allowed_origins"]
        if not isinstance(origins, list) or len(origins) > 20 or len(set(origins)) != len(origins):
            raise ValueError("invalid origin allowlist")
        for origin in origins:
            parsed = urlparse(origin) if isinstance(origin, str) else None
            if (
                parsed is None
                or parsed.scheme != "https"
                or not parsed.netloc
                or origin != f"{parsed.scheme}://{parsed.netloc}"
            ):
                raise ValueError("invalid allowed origin")
        if not manifest["enabled"]:
            return {
                "enabled": False,
                "package_version": manifest["package_version"],
                "license_name": manifest["license_name"],
                "attribution": manifest["attribution"],
                "updated_at": updated.isoformat(),
                "is_stale": datetime.now(UTC) > updated + timedelta(days=stale_days),
                "style": None,
            }
        style_file = (manifest_file.parent / manifest["style_file"]).resolve()
        if manifest_file.parent not in style_file.parents or style_file.stat().st_size > 1_000_000:
            raise ValueError("style escapes package or is too large")
        body = style_file.read_bytes()
        if hashlib.sha256(body).hexdigest() != manifest["style_sha256"]:
            raise ValueError("style checksum mismatch")
        style = json.loads(body)
        if (
            style.get("version") != 8
            or not isinstance(style.get("sources"), dict)
            or not isinstance(style.get("layers"), list)
        ):
            raise ValueError("invalid MapLibre style")
        allowed = set(origins)
        for value in _remote_urls(style):
            parsed = urlparse(value)
            if not parsed.scheme:
                continue
            host = (parsed.hostname or "").rstrip(".").lower()
            if host == "tile.openstreetmap.org" or host.endswith(".tile.openstreetmap.org"):
                raise ValueError("public OSM tiles are prohibited")
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if parsed.scheme != "https" or origin not in allowed:
                raise ValueError("style references an unapproved tile origin")
        return {
            "enabled": True,
            "package_version": manifest["package_version"],
            "license_name": manifest["license_name"],
            "attribution": manifest["attribution"],
            "updated_at": updated.isoformat(),
            "is_stale": datetime.now(UTC) > updated + timedelta(days=stale_days),
            "style_sha256": manifest["style_sha256"],
            "style": style,
        }
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise MapPackageUnavailable("MAP_PACKAGE_INVALID_OR_UNAVAILABLE") from exc

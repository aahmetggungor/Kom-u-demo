# Map/GIS package evidence — 2026-09-16

The local style manifest loader verifies exact fields, bounded metadata, timezone-aware update time, style path confinement, 1 MB size, SHA-256, MapLibre v8 structure and allowed HTTPS origins. Public OpenStreetMap raster tiles are explicitly rejected. Missing, disabled or invalid packages return a fixed disabled response; the React case list and blank coordinate workspace continue to operate.

GIS imports now require dataset version, licence, provenance, source update time, stale interval and canonical GeoJSON SHA-256. Geometry supports bounded Point, MultiPoint, LineString, MultiLineString, Polygon and MultiPolygon with layer-kind restrictions, closed rings, WGS84 coordinates, 200 features and 5,000 positions. The API calculates staleness and the UI displays source, version, licence/date and warnings. Migration 0009 upgraded existing rows to explicit `legacy`/`UNREVIEWED` metadata; those values are not operational approval.

Unit/API tests cover admin/tenant isolation, checksum mismatch, invalid bounds/properties, polygon closure, multi geometries, layer-kind mismatch, style tampering, public tile rejection and disabled package behavior. Eleven web tests and the production TypeScript/Vite build pass with Polygon/Multi rendering paths and package fallback compiled. The synthetic package contains a blank local style only; no tile download or municipal data is claimed.

Real pilot acceptance remains blocked on licensed style/tile files, municipal hospital/assembly/shelter/road datasets, data-owner freshness policy, browser outage/render checks against those exact packages and institutional legal/security approval. See `docs/operations/MAP_GIS_ONBOARDING.md`.

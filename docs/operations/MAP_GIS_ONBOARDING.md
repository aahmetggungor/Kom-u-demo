# Institutional map and GIS package onboarding

Updated 2026-09-16. No licensed municipal map or operational GIS dataset has been supplied. Current evidence uses conspicuously synthetic fixtures.

## Required map package

Provide a MapLibre style v8 JSON and a manifest with package version, source update time, stale-after interval, licence name, attribution, style filename, SHA-256 and allowed HTTPS tile origins. The style file must be at most 1 MB and remain inside the mounted package directory. Public `tile.openstreetmap.org` is rejected. Remote glyph, sprite, TileJSON and tile URLs must use HTTPS and match an explicit allowed origin. Relative URLs are permitted when the deployment reverse proxy serves licensed/offline assets locally.

Mount the package read-only and set `KOMSU_MAP_PACKAGE_MANIFEST` to the manifest path visible to the API. A missing, disabled, tampered or invalid package returns a fixed disabled result. The browser then keeps the case list and blank coordinate workspace available. It never substitutes an unlicensed public basemap.

The institution must supply licence/attribution text, permitted users and geography, offline/cache rights, redistribution limits, update cadence, expiry/renewal owner, tile/style versions, checksums, expected storage, zoom coverage, tile origin/certificate details and outage/SLA contacts.

## Required GIS datasets

For hospitals, assembly areas, shelters and closed roads, provide WGS84 GeoJSON plus:

- dataset owner and operational contact;
- dataset version, provenance, licence, source update timestamp and stale-after policy;
- canonical GeoJSON SHA-256;
- field definitions and semantics for active/closed/capacity/accessibility where approved;
- geometry expectations and geographic coverage;
- update/revocation process, emergency refresh SLA and authoritative source;
- privacy/security classification and whether any feature must be restricted by tenant/role.

The current import accepts at most 200 features and 5,000 coordinate positions. Hospitals, assembly areas and shelters accept Point/MultiPoint/Polygon/MultiPolygon. Closed roads accept LineString/MultiLineString. Polygon rings must be closed. Only a bounded plain `name` property is accepted; remote icons, HTML and executable properties are rejected. Imports require the admin role and are tenant-scoped.

The UI shows provenance, dataset version, licence, source date and a stale warning. Data being visible does not verify that a facility is open, reachable or suitable for dispatch. Operations must define an independent verification and emergency correction process.

## Acceptance checklist

1. Legal/licensing review confirms online/offline rendering, caching, attribution and incident use.
2. Security verifies read-only mount, allowed origins, TLS, secrets, CSP/reverse-proxy paths and no public fallback.
3. Data owner signs version/checksum/update cadence and stale policy for every layer.
4. Contract tests cover tampered style/data, stale metadata, unsupported/oversized geometry, public tile URLs and package outage.
5. Browser checks cover Polygon/Multi rendering, layer toggles, attribution/freshness, package disabled and tile outage while case list/manual workflow remains usable.
6. Pilot evidence records named files, checksums, licences, provider contacts, test timestamps and approval expiry.

`data/map-package.synthetic/` and `scripts/seed_gis_demo.py` are development fixtures only. They contain no operational facility, road or licensed basemap data.

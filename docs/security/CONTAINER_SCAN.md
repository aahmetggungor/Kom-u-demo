# Local container vulnerability scan — 2026-09-15

Trivy 0.74.0 scanned exported local image archives. Scanner image was pinned to `sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969`, with read-only container root, dropped capabilities and no Docker socket. Only the scan directory was mounted; application `.env` files were excluded from image builds. Official references: [Trivy release](https://github.com/aquasecurity/trivy/releases/tag/v0.74.0), [container scanning](https://trivy.dev/docs/latest/target/container_image/).

Counts below are package/CVE entries, not unique vulnerabilities or proven exploit paths. Exact image IDs, report hashes, severities, package versions and vendor links are in `container-scan-summary.json`.

| Target | Before critical/high | After critical/high | After high/critical entries with vendor fix |
|---|---:|---:|---:|
| API Debian packages | 3 / 53 | 0 / 44 | 0 |
| API Python packages | 0 / 0 (6 lower-severity entries) | 0 / 0 (no entries) | 0 |
| Database Debian packages | 20 / 162 | 16 / 111 | 0 |
| Database gosu Go metadata | 4 / 52 | 4 / 52 | 56 |

Changes: refresh Debian packages during image build; update build-time pip to 26.2.1 and remove the unnecessary installer from final API/worker/migration images. PostgreSQL moved from 17.6 to 17.11 within the same major version. A custom-format database backup was taken first. All 12 demo reports remained and all 57 Python tests passed against the updated PostgreSQL installation; API health and migrations passed.

**Unresolved:** vendor-unfixed OS findings remain; there is no clean-container or production-readiness claim. `gosu` was inherited from the pgvector image and remains flagged by Go version metadata. The [upstream security policy](https://github.com/tianon/gosu/security) explains that many Go standard-library CVEs do not apply to its compiled functionality. That policy is not a project-specific reachability assessment: these findings remain recorded, not suppressed or accepted. Assess each relevant path and consider a maintained base image or a reviewed rebuild before pilot release. Scanner severity mapping can differ by vendor; lack of a vendor fix does not mean harmlessness.

This is a local bounded scan. Remote CI security execution, penetration testing, production deployment and field validation have not occurred.

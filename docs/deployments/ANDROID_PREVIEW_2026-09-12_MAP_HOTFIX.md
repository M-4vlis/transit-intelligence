# Android preview v0.1.2 map hotfix

Date: 2026-09-12

Target: Android ARM64 (`arm64-v8a`)

## Device validation of v0.1.1

- application startup: passed;
- live API counters and markers: passed;
- GTFS route search: passed with route 870;
- local favorite persistence: passed;
- raster basemap: failed with OpenStreetMap HTTP 403 policy tiles.

## Cause and correction

React Native image requests reached the volunteer OpenStreetMap tile service
directly with a generic HTTP client identity. The v0.1.2 application now reads
tiles only through the Transit edge. The edge sends a stable, contactable user
agent, preserves source cache headers, caches successful tiles for seven days,
rate-limits the endpoint, and permits only numeric tile paths. The edge remains
disconnected from the data network.

## Build and verification

- implementation commits: `2595d31`, `2bf2661`;
- CI run: `34667940968` (`success`);
- APK run: `34667954550` (`success`);
- GitHub artifact: `10289787626`, expires 2026-09-19;
- APK size: 40,165,042 bytes;
- APK SHA-256: `eff4f4258a53c943f8676c0373d0fc13846124ba442bc377f592345ebeaf2ef7`;
- distribution ZIP SHA-256: `1a6821f11722c43afb172738f0e0f25ae752a975d0a0d4c6ea72e1d7b66eb294`;
- Android v2+ signing block: present;
- native architecture: only `arm64-v8a`;
- direct OpenStreetMap host reference in APK: absent;
- Transit tile route reference in APK: present;
- internal edge smoke: PNG response and second-request cache hit passed;
- external HTTPS tile response: HTTP 200, `image/png`, cache hit;
- full public distribution download: HTTP 200 with matching SHA-256;
- production collection continued successfully with zero rejected records while
  the edge was replaced.

The distribution ZIP is unencrypted and exists only to make the APK easier to
download through managed-device filters. The public preview endpoints are
temporary and must be removed after device validation.

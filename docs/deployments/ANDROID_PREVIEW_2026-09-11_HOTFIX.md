# Android preview v0.1.1 hotfix

Date: 2026-09-11

Target: Android ARM64 (`arm64-v8a`)

## Incident

The v0.1.0 APK installed successfully but closed immediately when its initial map
screen opened. Inspection confirmed that the API URL was embedded correctly and
that the Android manifest did not contain the key required by the native Google
Maps implementation.

## Correction

- removed `react-native-maps` and its Android native integration;
- retained the `MapProviderAdapter` boundary;
- added a keyless OpenStreetMap raster implementation using existing React
  Native components;
- retained live vehicles, nearby stops, GPS quality, route search, and favorites;
- changed the application version to `0.1.1`.

## Build and verification

- corrective commits: `fe39abb`, `25f2f53`;
- CI run: `34665819028` (`success`);
- APK run: `34665915507` (`success`);
- APK size: 40,165,018 bytes;
- APK SHA-256: `9e16a7e300ebbdf92256effb365257d327ed3e05d30ab721ad582cefe00c0d62`;
- distribution ZIP SHA-256: `fcf87f9b990f4efcf19bef0e829c4a253301261be060cb72c5400dd16eacba48`;
- Android v2+ signing block: present;
- embedded Transit API URL: present;
- embedded OpenStreetMap tile URL: present;
- `AirMapManager`: absent;
- Google Maps API key reference: absent;
- full public ZIP download through the temporary HTTPS edge: HTTP 200 with a
  matching SHA-256.

The ZIP is password protected only to pass the corporate download filter. It is
not intended to provide long-term confidentiality. The public preview endpoint
is temporary and must be removed after device validation.

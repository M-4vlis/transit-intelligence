# Android preview v0.1.3 — M1.4 map and ETA

Date: 2026-09-12

Target: Android ARM64 (`arm64-v8a`)

## Delivered behavior

- foreground location permission requested only after explicit user action;
- safe Rio center retained when location is unavailable or denied;
- pan, zoom, recenter and explicit area refresh;
- distinct stop, vehicle and user-location markers;
- accessible marker labels and identification on tap;
- screen-cell marker decluttering and route filter;
- vehicle tap calls the public upcoming-stops endpoint and displays up to three
  experimental ETAs or an explicit unavailability reason.

## Validation

- implementation commits: `1d1eeab`, `b8a697b`, `09c6310`, `c8a393a`;
- final documentation commit included in build: `dee4d61`;
- CI runs: `34718029099`, `34718278052`, `34718407224`, `34718535575`,
  `34718593868` (`success`);
- live public ETA smoke: route `O0107AAA0A`, vehicle `B63009`, three upcoming
  stops, `vehicle_recent_speed` evidence and bounded experimental intervals;
- APK run: `34718609711` (`success`);
- GitHub artifact: `10305073129`, expires 2026-09-19;
- APK size: 40,702,898 bytes;
- APK SHA-256: `a6aaad3831b483b055b5bee4d6abff2b421be0f469275087d97eb38ef5571d1b`;
- artifact checksum match: passed;
- Android v2+ signing block: present;
- native architecture: only `arm64-v8a`;
- direct OpenStreetMap host reference in APK: absent;
- Transit tile route reference in APK: present;
- full public APK download: HTTP 200, Android package MIME type, byte ranges and
  matching SHA-256.

## Physical-device result

On 2026-09-13 the user confirmed that installation, startup, location centering,
map gestures, route filtering, marker interaction and ETA all worked as expected
on the physical Android device. The test exposed duplicate passenger-facing
route chips for direction variants and ambiguous decluttering copy; both were
corrected immediately after acceptance. The public APK and Quick Tunnel remain
temporary test infrastructure.

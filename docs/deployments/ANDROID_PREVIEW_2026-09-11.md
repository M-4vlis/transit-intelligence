# Android preview v0.1.0

Date: 2026-09-11

Target: Android ARM64 (`arm64-v8a`)

## Build

- Git commit: `1f205a16c7a2b42aa3e122f8e2ebbfd017ca1f11`
- GitHub Actions run: `34651468370`
- Workflow: `Android preview APK`
- Result: `success`
- APK size: 41,976,472 bytes
- SHA-256: `eee121afe9b528c424e70f410c0319aaf194c2fdfea029e26582e1f78cb67ee8`
- GitHub artifact expiration: 2026-09-18

The application was built with the temporary HTTPS API endpoint supplied by a
Cloudflare Quick Tunnel. The endpoint is suitable only for this preview and may
change if the tunnel container restarts.

## Verification

- repository CI: `success`;
- APK checksum matches the checksum produced by the remote build;
- Android manifest and DEX bytecode are present;
- Android v2+ signing block is present;
- native library is present for `arm64-v8a`;
- no `armeabi-v7a`, `x86`, or `x86_64` native libraries are included;
- external route query through the preview edge: `PASS`;
- private readiness endpoint through the preview edge: `404`;
- mutation through the preview edge: `403`;
- VPS services `api`, `postgres`, `redis`, `rio-ingestion`, `edge-proxy`, and
  `cloudflared-quick`: running; health-enabled services: healthy.

## Scope of this preview

- live vehicle map;
- route search;
- route vehicles;
- nearby stops and vehicles;
- local favorites;
- effective GPS age and quality display.

This preview is not a production release. It uses a temporary tunnel URL and a
test signing identity, and it is distributed outside Google Play.

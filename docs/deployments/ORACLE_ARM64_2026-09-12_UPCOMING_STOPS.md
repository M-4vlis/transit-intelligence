# Oracle ARM64 — live upcoming-stop matching — 2026-09-12

## Outcome

The API can now match a live vehicle to its active GTFS route, shape and next
stops through:

`GET /v1/routes/{route_id}/vehicles/{vehicle_id}/upcoming-stops`

This is a matching endpoint, not an ETA. It exposes exact-trip versus
route-shape fallback evidence and refuses projections more than 250 metres
from the shape.

## Verification

- commit: `8972426`;
- CI run: `34700927907` (`success`), including a real PostGIS projection test;
- local suite: 117 passed, 6 integration tests deselected;
- only the API image and container were replaced;
- public HTTPS sample: vehicle `A63515`, route `O0107AAA0A`, shape `nasu`;
- fallback method: `route_shape_pattern`;
- projection distance: approximately 211 metres;
- five upcoming stops returned; first stop: `Anfilófio de Carvalho`;
- API health: healthy, zero restarts;
- final stack smoke: database, cache and recent position passed;
- latest observation age in final smoke: approximately 36 seconds;
- all six long-running services active;
- production environment SHA-256 unchanged;
- destructive retention remained disabled and the Android package was not
  changed.

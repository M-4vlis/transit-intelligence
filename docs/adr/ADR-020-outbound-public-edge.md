# ADR-020 — Outbound-only public API edge

## Status

Accepted on 2026-09-10.

## Context

The Oracle host is shared with Atualiza_materiais, whose public HTTPS API owns
TCP 443. The operator network blocks outbound SSH on ports 22 and 22022, so
administration must also traverse 443. A host-level protocol multiplexer sends
TLS to the existing Caddy proxy and key-only SSH to a loopback-only daemon. The
Transit API must still avoid publishing host ports.

## Decision

Use a remotely managed Cloudflare Tunnel as the public transport and place an
isolated Nginx policy proxy between `cloudflared` and FastAPI.

- the connector makes outbound-only connections and publishes no host port;
- `cloudflared` and FastAPI do not share a Docker network;
- Nginx is the only bridge between tunnel and API networks;
- only bounded read traffic under `/v1/` is proxied;
- health, metrics, documentation and other paths fail closed;
- the connector token is mounted from a protected file, never an environment
  value committed to Git;
- public activation requires a real hostname, TLS validation and external smoke.

## Consequences

TCP 443 safely carries both the existing Atualiza_materiais HTTPS API and
key-only administrative SSH; direct port 22 ingress remains denied. Transit
still needs no inbound HTTP/HTTPS rule because its connector is outbound-only.
Cloudflare becomes a public-edge dependency, but the API contract remains
portable. Nginx keeps a minimum local abuse-control baseline if Cloudflare plan
features change. Tunnel configuration must point only to
`http://edge-proxy:8080`.

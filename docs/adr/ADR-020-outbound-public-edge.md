# ADR-020 — Outbound-only public API edge

## Status

Accepted on 2026-09-10.

## Context

The Oracle host already uses TCP 443 for restricted SSH access. Reassigning that
port risks losing the reliable administration path, while publishing the API on
an alternate host port would expose the origin and bypass edge controls.

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

SSH can remain on port 443, and Oracle ingress does not need HTTP/HTTPS rules.
Cloudflare becomes a public-edge dependency, but the API contract remains
portable. Nginx keeps a minimum local abuse-control baseline if Cloudflare plan
features change. Tunnel configuration must point only to
`http://edge-proxy:8080`.

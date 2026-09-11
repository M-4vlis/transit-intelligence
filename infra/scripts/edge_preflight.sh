#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf 'OK: %s\n' "$*"; }

[[ -f "$ENV_FILE" ]] || fail "missing production env file: $ENV_FILE"

read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

hostname="$(read_env PUBLIC_API_HOSTNAME)"
[[ "$hostname" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ ]] \
  || fail "PUBLIC_API_HOSTNAME must be a lowercase DNS hostname"
[[ "$hostname" == *.* ]] || fail "PUBLIC_API_HOSTNAME must contain a DNS suffix"
[[ "$hostname" != *.example.com ]] || fail "replace the example PUBLIC_API_HOSTNAME"
info "public API hostname is syntactically valid"

token_file="$(read_env CLOUDFLARE_TUNNEL_TOKEN_FILE)"
if [[ -z "$token_file" ]]; then
  token_file="$ROOT_DIR/.secrets/cloudflare-tunnel-token"
elif [[ "$token_file" != /* ]]; then
  fail "CLOUDFLARE_TUNNEL_TOKEN_FILE must be an absolute path"
fi

[[ -f "$token_file" ]] || fail "missing Cloudflare tunnel token file: $token_file"
mode="$(stat -c '%a' "$token_file" 2>/dev/null || true)"
case "$mode" in
  600|400) info "tunnel token file permissions are restrictive ($mode)" ;;
  *) fail "set tunnel token file permissions to 600 (current: ${mode:-unknown})" ;;
esac

token_length="$(tr -d '\r\n' < "$token_file" | wc -c)"
(( token_length >= 50 )) || fail "Cloudflare tunnel token is unexpectedly short"
info "tunnel token file is populated"

# TCP 443 is shared by a protocol multiplexer. Refuse a direct sshd listener,
# which would bypass the multiplexer and make the co-resident HTTPS API fail.
if command -v sshd >/dev/null 2>&1 \
  && sshd -T 2>/dev/null \
    | awk '$1 == "port" && $2 == "443" { found = 1 } END { exit found ? 0 : 1 }'; then
  fail "direct sshd must not claim TCP 443; the host multiplexer owns it"
fi
info "direct sshd does not bypass the shared TCP 443 multiplexer"

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  --profile edge \
  config --quiet
info "edge compose configuration is valid"

printf '\nEdge preflight passed. No service was started.\n'

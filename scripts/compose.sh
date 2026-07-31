#!/usr/bin/env bash
set -euo pipefail

SHARED_COMPOSE_FILE="/Users/binarydev/Program/General/service/docker-compose.yml"

if [[ ! -f "$SHARED_COMPOSE_FILE" ]]; then
  printf 'Shared service compose file not found: %s\n' "$SHARED_COMPOSE_FILE" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  exec docker compose -f "$SHARED_COMPOSE_FILE" "$@"
fi

if command -v docker-compose >/dev/null 2>&1; then
  exec docker-compose -f "$SHARED_COMPOSE_FILE" "$@"
fi

printf 'Neither "docker compose" nor "docker-compose" is available.\n' >&2
exit 1

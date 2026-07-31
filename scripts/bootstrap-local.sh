#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
COMPOSE="$ROOT_DIR/scripts/compose.sh"

ensure_docker_daemon() {
  if docker info >/dev/null 2>&1; then
    return
  fi

  printf '[bootstrap] docker daemon is not running. Start Docker first, then rerun bootstrap.\n' >&2
  exit 1
}

copy_env_if_missing() {
  local example_path="$1"
  local target_path="${example_path%.example}"

  if [[ -f "$target_path" ]]; then
    printf '[bootstrap] keeping existing %s\n' "$target_path"
    return
  fi

  cp "$example_path" "$target_path"
  printf '[bootstrap] created %s from example\n' "$target_path"
}

wait_for_redis() {
  local retries=60

  until "$COMPOSE" exec -T redis redis-cli ping 2>/dev/null | grep -q '^PONG$'; do
    retries=$((retries - 1))
    if [[ "$retries" -le 0 ]]; then
      printf '[bootstrap] redis did not become ready in time\n' >&2
      return 1
    fi
    sleep 2
  done

  printf '[bootstrap] redis is ready\n'
}

wait_for_postgres() {
  local retries=60

  until "$COMPOSE" exec -T postgres pg_isready -U postgres -d vibecoding_starter >/dev/null 2>&1; do
    retries=$((retries - 1))
    if [[ "$retries" -le 0 ]]; then
      printf '[bootstrap] postgres did not become ready in time\n' >&2
      return 1
    fi
    sleep 2
  done

  printf '[bootstrap] postgres is ready\n'
}

copy_env_if_missing "apps/web/.env.example"
copy_env_if_missing "apps/api/.env.example"
copy_env_if_missing "apps/worker/.env.example"

ensure_docker_daemon

printf '[bootstrap] starting local stack\n'
"$COMPOSE" up -d

wait_for_postgres
wait_for_redis

printf '[bootstrap] installing API Python dependencies\n'
(cd apps/api && uv sync --all-groups)

printf '[bootstrap] applying API database migrations\n'
(cd apps/api && uv run alembic upgrade head)

printf '[bootstrap] generating merged openapi spec\n'
(cd apps/api && uv run python -m app.export_openapi)

printf '[bootstrap] local development infrastructure is ready\n'
"$COMPOSE" ps

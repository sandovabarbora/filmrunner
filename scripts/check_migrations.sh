#!/usr/bin/env sh
# One Alembic head only: two shifts adding migrations from the same parent
# would otherwise break `alembic upgrade head` in the release command.
set -eu
PY="${PYTHON:-python3}"
case "$PY" in /*) ;; */*) PY="$(pwd)/$PY" ;; *) ;; esac
cd "$(dirname "$0")/../backend"
count=$("$PY" -m alembic heads | grep -c "(head)" || true)
if [ "$count" -ne 1 ]; then
  echo "expected exactly one Alembic head, found $count; run: alembic merge -m 'merge' <rev1> <rev2>"
  "$PY" -m alembic heads
  exit 1
fi
echo "alembic: one head"

#!/usr/bin/env bash
# Run from the v16 bench; synthetic tests only. Never point at production.
set -euo pipefail
[ -x env/bin/python ] && [ -d sites/hrms-v16.localhost ] || { echo 'Run from the isolated v16 bench.'; exit 1; }
env/bin/python apps/workforce_suite/scripts/release_smoke.py hrms-v16.localhost
# Domain-spanning executable contract: each fixture cleans its synthetic records.
# The full suite includes persona negatives, native E2E and live isolated worker.
exec env/bin/python -m pytest apps/workforce_suite/workforce_suite/tests -q --disable-warnings "$@"

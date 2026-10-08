#!/usr/bin/env bash
# Run from an isolated v16 bench; synthetic tests only. Never use production.
set -euo pipefail
: "${FRAPPE_TEST_SITE:?Set an explicit disposable integration site}"
: "${FRAPPE_TEST_SITES_PATH:?Set the isolated bench sites directory}"
[ -x env/bin/python ] && [ -d "$FRAPPE_TEST_SITES_PATH/$FRAPPE_TEST_SITE" ] || { echo 'Run from the isolated v16 bench.'; exit 1; }
export FRAPPE_TEST_BENCH="$PWD"
env/bin/python apps/workforce_suite/scripts/release_smoke.py "$FRAPPE_TEST_SITE"
# The full suite includes persona negatives, native E2E and a live isolated worker.
exec env/bin/python -m pytest apps/workforce_suite/workforce_suite/tests -q --disable-warnings "$@"

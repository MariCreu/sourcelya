#!/bin/sh
set -e
alembic upgrade head

# Only starts anything when explicitly turned on (MALWARE_SCAN_PROVIDER=
# clamav) — a no-op otherwise, so this never changes behavior while the
# default "stub" scanner is active. Runs in the background: clamd refuses
# to start at all before freshclam finishes downloading the virus
# database, which can take a while, and the app must not block its own
# boot on that. Anything uploaded before clamd is ready gets a clean 503
# (MalwareScanUnavailableError, fail closed) instead of a broken upload.
if [ "$MALWARE_SCAN_PROVIDER" = "clamav" ]; then
  (freshclam --quiet && clamd --config-file=/etc/clamav/clamd.conf) &
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000

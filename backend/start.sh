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

# Drop root before running the actual web server — the setup above
# (migrations, optionally starting clamd) is the only reason this
# process starts as root at all. See the Dockerfile for the user.
exec su -s /bin/sh appuser -c "uvicorn app.main:app --host 0.0.0.0 --port 8000"

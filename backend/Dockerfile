FROM python:3.11-slim

WORKDIR /app

# clamav-daemon/clamav-freshclam are only *started* when
# MALWARE_SCAN_PROVIDER=clamav (see start.sh) — installing them
# unconditionally means turning real scanning on later is just an env var
# change, not a rebuild. See docs/PRODUCTION-READINESS.md for the tradeoff
# (bigger image, virus DB re-downloaded on every boot since Render's
# filesystem isn't persistent across deploys/restarts).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc clamav-daemon clamav-freshclam \
    && rm -rf /var/lib/apt/lists/* \
    # clamd's default config only listens on a local unix socket;
    # ClamAVMalwareScanner (app/integrations/malware/clamav_scanner.py)
    # talks to it over TCP, matching CLAMAV_HOST/CLAMAV_PORT's defaults.
    && printf 'TCPSocket 3310\nTCPAddr 127.0.0.1\n' >> /etc/clamav/clamd.conf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The container starts as root (start.sh needs it to run migrations and,
# when MALWARE_SCAN_PROVIDER=clamav, start clamd) but the actual
# internet-facing process — uvicorn, parsing every request and every
# supplier-uploaded file — drops to this unprivileged user before exec
# (see the last line of start.sh). Standard privilege-drop pattern: root
# only does setup, the process handling untrusted input never has it.
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

EXPOSE 8000

CMD ["./start.sh"]

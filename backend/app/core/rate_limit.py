from slowapi import Limiter
from slowapi.util import get_remote_address

# In-memory storage (slowapi's default) is fine as long as this API runs as
# a single instance (see Render's `numInstances: 1`, docs/PRODUCTION-
# READINESS.md) — scaling to multiple instances would need a shared
# backend (e.g. Redis) since counts wouldn't be seen across processes.
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

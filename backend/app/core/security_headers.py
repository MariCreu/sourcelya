from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
    # HSTS is safe to always send: browsers ignore it over plain HTTP (local
    # dev), and Render/Cloudflare already terminate TLS for every real
    # deployment of this API.
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds a standard set of defensive response headers. This is a JSON API
    with no templates or user-supplied HTML to render, so there's no CSP
    here — the frontend (a separate static SPA) is where a content-security
    policy would actually do something.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in _HEADERS.items():
            response.headers.setdefault(header, value)
        return response

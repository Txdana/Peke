"""Peke MCP Streamable HTTP Transport Server with Bearer Auth and Host/Origin Protection."""

import logging
from collections.abc import Callable

from mcp.server import MCPServer
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from peke.mcp.security import get_or_create_mcp_token, verify_mcp_token

logger = logging.getLogger(__name__)


class MCPSecurityMiddleware(BaseHTTPMiddleware):
    """Middleware validating Host, Origin, and Bearer Token for HTTP access."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Validate Host header
        host = request.headers.get("host", "").lower()
        if not (host.startswith("127.0.0.1") or host.startswith("localhost")):
            logger.warning("Rejected invalid Host header: %r", host)
            return JSONResponse({"error": "Forbidden: invalid Host header"}, status_code=403)

        # Validate Origin header if present
        origin = request.headers.get("origin", "").lower()
        if origin:
            if not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
                logger.warning("Rejected invalid Origin header: %r", origin)
                return JSONResponse({"error": "Forbidden: invalid Origin header"}, status_code=403)

        # Validate Bearer Token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse({"error": "Unauthorized: missing or invalid Authorization header"}, status_code=401)

        token = auth_header[7:].strip()
        if not verify_mcp_token(token):
            return JSONResponse({"error": "Unauthorized: invalid bearer token"}, status_code=401)

        return await call_next(request)


def create_http_app(server: MCPServer) -> Starlette:
    """Wrap MCPServer's streamable_http_app with security middleware."""
    base_app = server.streamable_http_app()
    app = Starlette(
        routes=base_app.routes,
        middleware=[Middleware(MCPSecurityMiddleware)],
    )
    return app


def run_http_server(server: MCPServer, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run Streamable HTTP server bound ONLY to 127.0.0.1."""
    if host != "127.0.0.1":
        raise ValueError("Peke MCP HTTP server binds to 127.0.0.1 ONLY for security.")

    import uvicorn

    token = get_or_create_mcp_token()
    logger.info("Starting Peke MCP HTTP server on http://127.0.0.1:%d/mcp (Token: %s...)", port, token[:8])

    app = create_http_app(server)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

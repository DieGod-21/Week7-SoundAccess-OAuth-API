"""SoundAccess — Secure Music API (Week 7).

Single ASGI application hosting three logically separated roles:

* Authorization Server  -> /oauth/*   (app/oauth)
* Resource Server       -> /api/*    (app/api)
* Demo OAuth Client     -> /client/* (frontend/, static demonstration UI)

The separation is architectural (modules, dependencies and documentation);
running them in one process keeps the local demo simple.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from .api.router import router as api_router
from .config import get_settings
from .oauth.router import router as oauth_router

logger = logging.getLogger("soundaccess")

app = FastAPI(
    title="SoundAccess API",
    version="1.0.0",
    description=(
        "API de música protegida con OAuth 2.0 y JWT.\n\n"
        "**Flujos soportados:** Authorization Code + PKCE (S256) y Client Credentials.\n\n"
        "**Scopes:** `catalog:read`, `profile:read`, `playlist:read`, `playlist:write`.\n\n"
        "Los endpoints `/api/*` requieren `Authorization: Bearer <JWT>`. "
        "Un token inválido o ausente produce **401**; un token válido sin el scope "
        "requerido (o sobre un recurso ajeno) produce **403/404**."
    ),
)

# CORS: explicit local origins only — wildcard is intentionally not used.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(oauth_router)
app.include_router(api_router)

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/client")


@app.get("/client", include_in_schema=False)
def client_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/client/callback", include_in_schema=False)
def client_callback():
    return FileResponse(FRONTEND_DIR / "callback.html")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak stack traces or internals to the API consumer."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"error": "internal_server_error"})


def custom_openapi():
    """Document bearer authentication so Swagger UI can send tokens."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema.setdefault("components", {}).setdefault("securitySchemes", {})[
        "BearerJWT"
    ] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Access token emitido por POST /oauth/token (expira en 15 min).",
    }
    for path, methods in schema["paths"].items():
        if path.startswith("/api/"):
            for op in methods.values():
                op["security"] = [{"BearerJWT": []}]
                responses = op.setdefault("responses", {})
                responses.setdefault("401", {"description": "Token ausente o inválido (invalid_token)"})
                responses.setdefault("403", {"description": "Token válido sin autorización suficiente (insufficient_scope)"})
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.cors import add_cors_middleware
from app.services import model_loader


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_loader.initialize()
    yield


app = FastAPI(
    title="무한맨틀 API",
    description="Korean word similarity game backend",
    version="2.0.0",
    lifespan=lifespan,
)

add_cors_middleware(app)
app.include_router(api_router)


# ── Exception handlers ───────────────────────────────────────────────────────
# Use {"error": "..."} for all error responses to preserve frontend compatibility.

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"error": str(exc)})

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import BASE_DIR, settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app startup and shutdown events."""
    # Aplica las migraciones pendientes de Alembic al arrancar (equivale a `alembic upgrade head`).
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(BASE_DIR / "alembic.ini")), "head")
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="FARADYNE Backend MVC API - Sistema de Protección contra Descargas Atmosféricas (IEC 62305 / IRAM 2184)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
ALLOWED_ORIGINS = [
    "http://localhost:1232",
    "http://127.0.0.1:1232",
    "http://localhost:1233", 
    "http://127.0.0.1:1233",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router under /api/v1
app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["Health"])
def root_status():
    """Root endpoint verifying API server status."""
    return {
        "status": "online",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "docs": "/docs",
        "api_v1": "/api/v1",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "ok", "db_configured": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=6500, reload=True)
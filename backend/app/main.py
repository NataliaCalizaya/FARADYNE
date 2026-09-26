from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_db_pool, init_db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app startup and shutdown events."""
    # Startup: Initialize PostgreSQL pool and verify DB connection
    init_db_pool()
    yield
    # Shutdown: Close database pool connection
    close_db_pool()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="FARADYNE Backend MVC API - Sistema de Protección contra Descargas Atmosféricas (IEC 62305 / IRAM 2184)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1232","http://127.0.0.1:1232"],
    allow_credentials=True,
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
    uvicorn.run("app.main:app", host="0.0.0.0", port=6500, reload=True)

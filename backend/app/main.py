"""
Main FastAPI Application Entrypoint.
Configures CORS, registers API v1 routers, handles startup database initialization,
and automatically bootstraps sample master data on Render Cloud container startup.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import init_db, SessionLocal
from app.db.bootstrap import bootstrap_database_if_empty
from app.api.v1.system import router as system_router
from app.api.v1.indicators import router as indicators_router
from app.api.v1.reports import router as reports_router
from app.api.v1.admin import router as admin_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management.
    Initializes database tables on application startup and auto-bootstraps
    master indicators, historical data and reports if the database is fresh.
    """
    # Startup actions: create DDL tables
    init_db()

    # Auto-seed if database is empty (crucial for cloud deploy on Render)
    db = SessionLocal()
    try:
        bootstrap_database_if_empty(db)
    finally:
        db.close()

    yield
    # Shutdown actions (if any)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Global Macroeconomic Intelligence & Daily Reporting Platform Backend API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# Configure Cross-Origin Resource Sharing (CORS)
origins = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
is_wildcard = "*" in origins or origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if is_wildcard else origins,
    allow_credentials=False if is_wildcard else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register v1 Routers
app.include_router(system_router, prefix=settings.API_V1_PREFIX)
app.include_router(indicators_router, prefix=settings.API_V1_PREFIX)
app.include_router(reports_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
def root():
    """Root landing endpoint with system summary."""
    return {
        "service": settings.PROJECT_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/system/health",
    }

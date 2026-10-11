"""
FastAPI Main Application Entry Point.
Initializes routers, CORS middleware, and application lifecycle.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.graph import router as graph_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.config import get_settings
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Runs initialization logic on startup and cleanup logic on shutdown.
    """
    settings = get_settings()
    # Ensure workspace directory exists
    settings.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    # Initialize database tables
    init_db()
    print(f"[{settings.APP_NAME}] Initialized database and workspace at: {settings.WORKSPACE_DIR.resolve()}")
    print(f"[{settings.APP_NAME}] CORS origins: {settings.CORS_ORIGINS}")
    yield
    print(f"[{settings.APP_NAME}] Shutting down.")


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "An offline-first, agentic code analysis and architecture visualization engine. "
        "Deterministically inspects repositories, extracts AST entities, constructs dependency graphs, "
        "runs static checks, and provides grounded local LLM explanations."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure Cross-Origin Resource Sharing (CORS) for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health_router)
app.include_router(projects_router)
app.include_router(graph_router)


@app.get("/", tags=["General"])
async def root():
    """Root endpoint providing quick navigation links."""
    return JSONResponse(
        content={
            "app_name": settings.APP_NAME,
            "version": "0.1.0",
            "status": "running",
            "documentation": "/docs",
            "health_check": "/health",
            "upload_endpoint": "POST /projects/upload",
        }
    )

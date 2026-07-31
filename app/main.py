from fastapi import FastAPI
from app.core.config import settings
from app.api.v1 import brief, timeline, search, commands, connections

app = FastAPI(
    title="Umbra Assistant API",
    description="The orchestration engine for the Umbra Personal Operating System",
    version="1.0.0",
    debug=settings.DEBUG
)

app.include_router(brief.router)
app.include_router(timeline.router)
app.include_router(search.router)
app.include_router(commands.router)
app.include_router(connections.router)

@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint verifying the server is online.
    """
    return {
        "status": "online",
        "app_name": "Umbra Assistant",
        "environment": settings.APP_ENV
    }

@app.get("/health", tags=["System"])
async def health_check():
    """
    Internal health check endpoint for monitoring system stability.
    """
    return {"status": "healthy"}

"""Version 1 API router composition."""

from fastapi import APIRouter

from app.api.v1.routes import (
    brief,
    session_auth,
    auth,
    commands,
    connections,
    search,
    timeline,
    type_registry,
    workspace,
)
from app.api.v1.routes.webhooks import calendar, email, whatsapp


api_router = APIRouter()

api_router.include_router(whatsapp.router, tags=["webhooks"])
api_router.include_router(email.router, tags=["webhooks"])
api_router.include_router(calendar.router, tags=["webhooks"])
api_router.include_router(brief.router, tags=["brief"])
api_router.include_router(timeline.router, tags=["timeline"])
api_router.include_router(search.router, tags=["search"])
api_router.include_router(commands.router, tags=["commands"])
api_router.include_router(connections.router, tags=["connections"])
api_router.include_router(type_registry.router, prefix="/types", tags=["types"])
api_router.include_router(workspace.router, tags=["workspaces"])

api_router.include_router(session_auth.router)
api_router.include_router(auth.router)

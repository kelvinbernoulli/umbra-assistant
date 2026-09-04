"""
Version 1 connections endpoints backing the "Connections Matrix" UI view.

Phase 1/2 scope: status listing + manual disconnect. Real OAuth
connect flows (Gmail/GCal) and WhatsApp webhook secret provisioning
are Phase 5 work — this gives the frontend a stable contract to build
against in the meantime.

The provider list is derived from the dynamic source registry
(app/db/type_registry.py) rather than hardcoded — add a new source there
and it automatically appears here as a connectable provider, minus
'manual' which isn't a real external integration.
"""

from __future__ import annotations
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user_id
from app.db.credential_store import list_connection_statuses, revoke_credential
from app.db.type_registry import list_sources
from app.models.schemas.connection import ConnectionResponse as ConnectionStatus

router = APIRouter()

NON_CONNECTABLE_SOURCES = {"manual"}  # exists as a source for manually-entered content, not a real integration


def _connectable_providers() -> list[str]:    
    return [str(s["name"]) for s in list_sources() if s["name"] not in NON_CONNECTABLE_SOURCES]


# 
@router.get("/connections", response_model=list[ConnectionStatus])
async def get_connections(user_id: str = Depends(get_current_user_id)):
    stored = {c["provider"]: c for c in list_connection_statuses(user_id)}
    results = []
    
    for provider in _connectable_providers():
        if provider in stored:
            c = stored[provider]
            results.append(ConnectionStatus(
                id=str(c["id"]),  # Ensure this is cast to string
                provider=provider, 
                status=str(c["status"]), 
                connected_at=cast(datetime | None, c.get("connected_at"))
            ))
        else:
            results.append(ConnectionStatus(
                id=None,
                provider=provider, 
                status="disconnected", 
                connected_at=None
            ))
            
    return results


@router.post("/connections/{provider}/disconnect", response_model=ConnectionStatus)
async def disconnect_provider(provider: str, user_id: str = Depends(get_current_user_id)):
    if provider not in _connectable_providers():
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    revoke_credential(user_id, provider)
    return ConnectionStatus(id=None, provider=provider, status="disconnected", connected_at=None)

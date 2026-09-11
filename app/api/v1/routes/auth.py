"""Google Calendar consent for an already authenticated Umbra user."""

from fastapi import APIRouter, Depends, Header, HTTPException
from google_auth_oauthlib.flow import Flow
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import get_current_user_id
from app.core.config import settings
from app.services.google_connections import cipher, save_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"


class GoogleAuthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=4096)


def allowed_origins():
    return settings.FRONTEND_ORIGINS


@router.post("/google/save")
def save_google_calendar_token(
    payload: GoogleAuthPayload,
    user_id: str = Depends(get_current_user_id),
    origin: str | None = Header(None),
    x_requested_with: str | None = Header(None),
):
    if origin not in allowed_origins() or x_requested_with != "XmlHttpRequest":
        raise HTTPException(403, "Invalid Google authorization origin or request header.")
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google Calendar is not configured on the server.")
    cipher()  # Check secure storage before consuming the single-use code.
    try:
        flow = Flow.from_client_config(
            {"web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }},
            scopes=[CALENDAR_SCOPE], redirect_uri=origin,
        )
        flow.fetch_token(code=payload.code, timeout=20)
        token = flow.credentials.refresh_token
        print(flow)
    except Exception:
        # OAuth exceptions can contain sensitive tokens or client credentials.
        raise HTTPException(400, "Google authorization failed. Please connect again.") from None
    if not token:
        raise HTTPException(400, "Google did not grant offline access. Remove Umbra from your Google account permissions and reconnect.")
    try:
        save_refresh_token(user_id, token)
    except Exception:
        raise HTTPException(503, "Could not save the Google connection. Please try again.") from None
    return {"status": "success", "message": "Google Calendar connected."}

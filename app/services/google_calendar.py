"""Google Calendar operations using only the signed-in user's credentials."""
from urllib.parse import quote

from fastapi import HTTPException
from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from requests.exceptions import RequestException

from app.core.config import settings
from app.services.google_connections import load_refresh_token


def calendar_request(user_id: str, method: str, calendar_id: str = "primary",
                     event_id: str | None = None, *, body: dict | None = None,
                     params: dict | None = None) -> dict:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google Calendar is not configured on the server.")
    token = load_refresh_token(user_id)
    # Refresh with the original grant; old read-only grants get a clear 403 on writes.
    credentials = Credentials(None, refresh_token=token,
                              token_uri="https://oauth2.googleapis.com/token",
                              client_id=settings.GOOGLE_CLIENT_ID,
                              client_secret=settings.GOOGLE_CLIENT_SECRET)
    url = "https://www.googleapis.com/calendar/v3/calendars/" + quote(calendar_id, safe="") + "/events"
    if event_id is not None:
        url += "/" + quote(event_id, safe="")
    try:
        with AuthorizedSession(credentials, refresh_timeout=20) as session:
            response = session.request(method, url, json=body, params=params, timeout=20)
    except RefreshError:
        raise HTTPException(409, "Google authorization expired or was revoked. Reconnect Google Calendar.") from None
    except (GoogleAuthError, RequestException):
        raise HTTPException(502, "Could not reach Google Calendar. Check your calendar before retrying a change.") from None
    if response.status_code == 401:
        raise HTTPException(409, "Reconnect Google Calendar to restore access.")
    if response.status_code == 403:
        raise HTTPException(403, "Google denied access. Reconnect with Calendar event permissions and check that this calendar is editable.")
    if response.status_code in (404, 410):
        raise HTTPException(404, "Calendar or event was not found.")
    if response.status_code == 429:
        raise HTTPException(429, "Google Calendar rate limit reached. Please try again later.")
    if response.status_code == 400:
        raise HTTPException(400, "Google Calendar rejected the event details.")
    if not response.ok:
        raise HTTPException(502, "Google Calendar could not complete the request. Check your calendar before retrying a change.")
    try:
        return response.json()
    except ValueError:
        raise HTTPException(502, "Google Calendar returned an invalid response.") from None

# umbra-assistant

Umbra Assistant is an ambient Personal Operating System (Personal OS) designed to unify fragmented communication streams, documents, and scheduling tools into a single, private dashboard. 

By leveraging a semantic vector database and open-source models, Umbra runs quietly in the background to eliminate inter-app friction, provide instant cross-app search, and generate automated morning briefs.

## Technical Stack
- **Orchestration:** LangChain
- **Vector Database (Long-Term Memory):** Pinecone
- **AI/Embeddings Ecosystem:** Hugging Face
- **Backend API Framework:** FastAPI

## Project Structure
- `app/api/`: Webhook listeners and API routing endpoints.
- `app/services/`: LLM orchestration and vector search logic.
- `app/core/`: Configuration layouts and environment security.

## Admin user analytics

The admin dashboard provides a registered-user total, searchable user list, and
per-user account/workspace summaries with active integration and stored-item
counts. It does not expose stored message or event contents. Access is enforced
by the backend using the signed-in Google account email; frontend navigation is
not an authorization boundary.

Set `ADMIN_EMAILS` in the backend environment to a JSON list of permitted email
addresses, for example `["admin@example.com"]`. Email matching is
case-insensitive. With an empty or unmatched allowlist, admin analytics requests
are denied. The current schema does not track account creation time or sign-in
activity, so those are not presented as user metrics.

## Render PostgreSQL deployment

The backend includes the PostgreSQL driver (`psycopg2-binary`). Create a Render
Postgres database in the same region and account as the backend, then use its
Internal Database URL for `DATABASE_URL` in the backend's Environment settings.
Use a `postgresql://` URL (or `postgresql+psycopg2://`), not `postgres://`.
Remove a SQLite `CREDENTIAL_DB_URL` override so Google integration credentials
use `DATABASE_URL`, or set it to the same PostgreSQL URL. Keep the existing
`CREDENTIAL_ENCRYPTION_KEY`.

Set the Render Start Command to:

```sh
python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Deploy and check that Alembic upgrades to `0006_google_sessions` before the
server starts. Verify Google sign-in and session restoration after a restart.
OAuth credential storage creates its table on the first integration connection.

Changing the URL creates an empty database; Alembic migrates schema, not existing
SQLite rows. If existing data matters, back up and transfer the live SQLite data
before changing environment settings or redeploying. Preserve user and workspace
IDs (including their relationship to Pinecone data), and transfer any separate
credential database with its encryption key. For a fresh start, users must sign
in and reconnect integrations.

Render's free Postgres databases expire after 30 days; select a suitable paid
plan for ongoing use. See [Render Postgres setup](https://render.com/docs/postgresql-creating-connecting)
and [free plan limits](https://render.com/docs/free).

## PostgreSQL integration tests

The default test suite uses isolated SQLite databases. PostgreSQL checks are opt-in and read `POSTGRES_DATABASE_URL` from `.env`.

Use a dedicated disposable database for `POSTGRES_DATABASE_URL`: these tests
create and drop application tables. Never point it at the live database.
If configured, integration tests run against it. Otherwise, they skip cleanly:

```powershell
.\umbra-env\Scripts\python.exe -m pytest -m postgres -q
```

For local development, you can use Docker:

```powershell
docker compose -f infra/docker-compose.yml up -d postgres
```

Stop it with:

```powershell
docker compose -f infra/docker-compose.yml down -v
```

## Scheduled ingestion retries

The retry worker can run inside the FastAPI process. Set these environment variables to enable it:

```dotenv
RETRY_SCHEDULER_ENABLED=true
RETRY_INTERVAL_SECONDS=300
RETRY_BATCH_LIMIT=100
```

The scheduler runs at most one retry batch at a time and is shut down with the application. The standalone command remains available:

```powershell
.\umbra-env\Scripts\python.exe -m app.workers.retry_failed --limit 100
```

## Google Calendar event editing

The backend supports these authenticated endpoints:

- `GET /api/v1/calendar/events`: list upcoming events, with `items` and Google's
  optional `nextPageToken`. Pass `page_token` for the next page, `limit` (1–250),
  and optional offset-aware `time_min` / `time_max` timestamps.
- `POST /api/v1/calendar/events`: create an event; returns the Google event (201).
- `PATCH /api/v1/calendar/events/{event_id}`: edit only supplied fields; returns
  the updated Google event. Other fields, including existing guests, are preserved.

All endpoints default to the user's `primary` calendar. Use `calendar_id` to
target another calendar the user can access. Credentials are selected from the
authenticated user; requests cannot supply a different user ID.

The current frontend and backend connection flow request `calendar.readonly`,
which is sufficient for the event list and briefs. The backend verifies the
scopes actually returned by Google and also accepts existing Calendar event or
full Calendar grants. Future event editing UI must explicitly request
`https://www.googleapis.com/auth/calendar.events` and explain the additional
permissions. Existing read-only grants cannot write events. Google Calendar API
must be enabled in the Google Cloud project that owns the OAuth client.

If Calendar fails with 403, the backend distinguishes Google's reason codes:
disabled API (503), quota/rate limits (429), missing consent (403), and organization
policy (403). Unknown read failures no longer tell users they need edit access.
Enable the API in Google Cloud for API-disabled errors; reconnect from Sources
for missing-consent errors. Reconnecting cannot enable a disabled Cloud API.

Example create body:

```json
{
  "summary": "Project planning",
  "description": "Discuss next steps",
  "location": "Office",
  "start": {"dateTime": "2026-10-01T10:00:00+01:00"},
  "end": {"dateTime": "2026-10-01T11:00:00+01:00"}
}
```

For all-day events, use `{"date": "2026-10-01"}` for start and
`{"date": "2026-10-02"}` for end (the end date is exclusive). Edits may contain
just `{"summary": "New title"}`. When changing times, provide both start and end.
Empty description/location strings clear those fields. Null fields are rejected.
Guest notifications default to `send_updates=none`; the UI can explicitly request
`send_updates=all` or `externalOnly` when saving edits to meetings with guests.

Browser calls must include the session cookie (`credentials: "include"`) and
`X-Requested-With: XmlHttpRequest` for mutations, as with other authenticated
Umbra changes. After a successful save, refresh the event list. A 409 means the
user must connect/reconnect; a 403 can mean missing edit consent or calendar
permissions. If a write times out, refresh the list before retrying to avoid
creating a duplicate event.

This repository contains the backend only. The companion frontend reads live events; it still needs
create/edit forms, and the updated Google consent scope wired to these endpoints.
Natural-language command execution remains unimplemented.

See Google's [event creation](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert)
and [partial event update](https://developers.google.com/workspace/calendar/api/v3/reference/events/patch) references.

## Runtime data requirements

Vector storage requires `PINECONE_API_KEY` and a configured Pinecone index.
Embeddings use the actual Hugging Face model locally (default:
`BAAI/bge-large-en-v1.5`); its weights must be cached or downloadable.
There is no in-memory vector store or synthetic embedding fallback.
Model and storage failures propagate to callers and ingestion retry handling.
Command execution returns HTTP 501 until implemented. GET /api/v1/brief/today now returns a factual daily overview from live Google Calendar events and the latest 100 workspace records, without Pinecone or a language model. Pass an IANA timezone (for example, timezone=Africa/Lagos); UTC is the default. Calendar failures are returned as calendar_notice with a null calendar_count, while saved activity remains available. The calendar summary covers the first 250 events and sets calendar_has_more if further pages exist. When configured, Hugging Face synthesizes this overview into an AI daily brief; otherwise the factual overview remains available.


## AI daily briefs (Hugging Face)

`GET /api/v1/brief/today` uses the configured hosted chat model after reading the
signed-in user's primary calendar and the authorized workspace's saved records.
No Pinecone index, embedding model or local model download is needed for briefs.

Set these variables in the backend environment (never in frontend VITE variables):

```dotenv
HUGGINGFACE_API_TOKEN=<token with Inference Providers permission>
HUGGINGFACE_SYNTHESIS_MODEL=<provider-supported chat model ID or endpoint URL>
HUGGINGFACE_INFERENCE_PROVIDER=auto
BRIEF_AI_ENABLED=true
BRIEF_LLM_TIMEOUT_SECONDS=15
```

The existing local model setting is preserved. Confirm that the model is served by
an inference provider available to your Hugging Face account. A Hub model existing
does not guarantee hosted inference availability. A 403 may require correcting
token permissions or model/provider access. Configure the same variables on the
backend host before deployment, install requirements, and restart the backend.
Set `BRIEF_AI_ENABLED=false` to use only the factual overview.

The prompt includes at most 20 events and 12 of the latest 100 saved records,
with capped text fields, dates, timezone and partial-data markers. Raw OAuth
credentials, account tokens, attendees and arbitrary record metadata are not sent.
Event descriptions and saved text are sent to Hugging Face/the selected inference
provider for processing. Each eligible brief load or refresh makes one generation
request; generated text is not persisted or cached. Empty workspaces skip inference.
The model receives no tools and cannot create events or execute commands.

The API returns `summary_source=ai` after successful synthesis. Missing configuration,
provider failure or incomplete output retains `summary_source=factual` and a public
`summary_notice`. Calendar errors remain in `calendar_notice`, and numeric counts
always come from source data. The frontend allows 90 seconds for calendar retrieval
and synthesis; the configurable model response timeout defaults to 15 seconds.
Provider errors are logged by exception class only, without prompts or tokens.
AI prose is not independently fact-checked; source events remain visible for review.

See the [Hugging Face inference client documentation](https://huggingface.co/docs/huggingface_hub/package_reference/inference_client).

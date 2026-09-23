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

## Runtime data

Vector storage requires `PINECONE_API_KEY` and a configured Pinecone index.
Embeddings use the actual Hugging Face model locally (default:
`BAAI/bge-large-en-v1.5`); its weights must be cached or downloadable.
There is no in-memory vector store or synthetic embedding fallback.
Model and storage failures propagate to callers and ingestion retry handling.
Morning briefs and command execution return HTTP 501 until implemented.

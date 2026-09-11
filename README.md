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

## PostgreSQL integration tests

The default test suite uses isolated SQLite databases. PostgreSQL checks are opt-in and read `POSTGRES_DATABASE_URL` from `.env`.

If `POSTGRES_DATABASE_URL` is configured, integration tests run against it. Otherwise, they skip cleanly:

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

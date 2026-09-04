# Umbra Assistant — Architecture & Implementation Roadmap

**Stack:** React 18 + TS + Vite · FastAPI (async) · LangChain · Pinecone · Hugging Face embeddings
**Author role:** Principal Software Architect / Product Planner
**Status:** Pre-implementation blueprint

---

## 1. Unified File & Folder Tree

```
umbra-assistant/
│
├── frontend/                              # React + Vite + TS
│   ├── public/
│   │   └── favicon.svg
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── routes/
│   │   │   ├── Dashboard.tsx              # Morning Brief view
│   │   │   ├── TimelineFeed.tsx
│   │   │   ├── ControlDeck.tsx            # command bar / search
│   │   │   └── ConnectionsMatrix.tsx      # integration/credential mgmt
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.tsx
│   │   │   │   ├── TopBar.tsx
│   │   │   │   └── Shell.tsx
│   │   │   ├── dashboard/
│   │   │   │   ├── BriefCard.tsx
│   │   │   │   ├── PriorityList.tsx
│   │   │   │   └── SourceBadge.tsx
│   │   │   ├── timeline/
│   │   │   │   ├── TimelineItem.tsx
│   │   │   │   └── TimelineFilterBar.tsx
│   │   │   ├── control-deck/
│   │   │   │   ├── CommandInput.tsx
│   │   │   │   ├── SemanticResultsList.tsx
│   │   │   │   └── QuickActionChips.tsx
│   │   │   └── connections/
│   │   │       ├── IntegrationCard.tsx
│   │   │       └── TokenStatusPill.tsx
│   │   ├── hooks/
│   │   │   ├── useMorningBrief.ts
│   │   │   ├── useTimelineStream.ts       # SSE/WebSocket subscription
│   │   │   ├── useSemanticSearch.ts
│   │   │   ├── useConnections.ts
│   │   │   └── useCommandParser.ts
│   │   ├── state/
│   │   │   ├── store.ts                   # Zustand root store
│   │   │   ├── briefSlice.ts
│   │   │   ├── timelineSlice.ts
│   │   │   ├── connectionsSlice.ts
│   │   │   └── uiSlice.ts
│   │   ├── api/
│   │   │   ├── client.ts                  # fetch/axios wrapper + auth header
│   │   │   ├── briefApi.ts
│   │   │   ├── timelineApi.ts
│   │   │   ├── searchApi.ts
│   │   │   └── connectionsApi.ts
│   │   ├── types/
│   │   │   ├── brief.ts
│   │   │   ├── timelineEvent.ts
│   │   │   ├── connection.ts
│   │   │   └── searchResult.ts
│   │   ├── styles/
│   │   │   └── tailwind.css
│   │   └── lib/
│   │       ├── formatters.ts
│   │       └── constants.ts
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/                               # Python + FastAPI
│   ├── app/
│   │   ├── main.py                        # app factory, router mounting
│   │   ├── api/
│   │   │   ├── deps.py                    # shared dependencies (auth, db)
│   │   │   ├── v1/
│   │   │   │   ├── router.py              # composes all versioned routers
│   │   │   │   └── routes/
│   │   │   │       ├── brief.py           # GET /brief/today
│   │   │   │       ├── timeline.py        # GET /timeline (+ SSE stream)
│   │   │   │       ├── search.py          # POST /search (semantic)
│   │   │   │       ├── commands.py        # POST /commands (NL task creation)
│   │   │   │       ├── connections.py     # CRUD for integration tokens
│   │   │   │       ├── type_registry.py   # source/document type routes
│   │   │   │       └── webhooks/
│   │   │   │           ├── whatsapp.py
│   │   │   │           ├── email.py
│   │   │   │           └── calendar.py
│   │   ├── services/
│   │   │   ├── ingestion/
│   │   │   │   ├── normalizer.py          # raw payload -> canonical Document
│   │   │   │   ├── chunker.py
│   │   │   │   └── pipeline.py            # orchestrates normalize->embed->upsert
│   │   │   ├── embeddings/
│   │   │   │   └── hf_embedder.py         # BAAI/bge-large-en-v1.5 wrapper
│   │   │   ├── vectorstore/
│   │   │   │   ├── pinecone_client.py
│   │   │   │   └── namespace_router.py    # tenant/user -> namespace mapping
│   │   │   ├── llm/
│   │   │   │   ├── synthesis_llm.py       # HF-hosted inference call
│   │   │   │   └── prompt_templates.py
│   │   │   ├── agent/
│   │   │   │   ├── orchestrator.py        # LangChain agent executor
│   │   │   │   ├── tools/
│   │   │   │   │   ├── search_memory_tool.py
│   │   │   │   │   ├── create_reminder_tool.py
│   │   │   │   │   ├── calendar_tool.py
│   │   │   │   │   └── summarize_tool.py
│   │   │   │   └── memory.py              # conversation/session memory
│   │   │   └── realtime/
│   │   │       └── event_bus.py           # pub/sub feeding SSE to frontend
│   │   ├── models/
│   │   │   ├── schemas/                   # Pydantic I/O models
│   │   │   │   ├── brief.py
│   │   │   │   ├── timeline_event.py
│   │   │   │   ├── search.py
│   │   │   │   ├── connection.py
│   │   │   │   └── webhook_payloads.py
│   │   │   └── domain/                    # internal dataclasses
│   │   │       └── document.py
│   │   ├── core/
│   │   │   ├── config.py                  # pydantic-settings BaseSettings
│   │   │   ├── security.py                # token encryption, auth
│   │   │   ├── logging.py
│   │   │   └── exceptions.py
│   │   └── db/
│   │       └── credential_store.py        # encrypted at-rest token storage (NOT Pinecone)
│   ├── tests/
│   │   ├── test_ingestion_pipeline.py
│   │   ├── test_agent_tools.py
│   │   └── test_api_routes.py
│   ├── .env.template
│   ├── pyproject.toml
│   └── requirements.txt
│
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── nginx.conf
│
├── docs/
│   └── architecture/  (this document + ADRs)
│
└── README.md
```

**Note on the credential store:** OAuth tokens and webhook secrets (WhatsApp, Gmail, GCal) should **not** live in Pinecone metadata or in plaintext `.env` at runtime — Pinecone is for semantic content, not secrets. Use an encrypted credential store (e.g., a small Postgres/SQLite table with field-level encryption, or a secrets manager like AWS Secrets Manager/HashiCorp Vault) referenced by `db/credential_store.py`. This matters given your stated "extreme data privacy" principle.

---

## 2. Frontend Client Schema & Architecture

### 2.1 View → Component Mapping

| View | Primary Components | Data Source |
|---|---|---|
| Dashboard | `BriefCard`, `PriorityList`, `SourceBadge` | `useMorningBrief()` → `GET /brief/today` |
| Timeline Feed | `TimelineItem`, `TimelineFilterBar` | `useTimelineStream()` → SSE `GET /timeline/stream` |
| Control Deck | `CommandInput`, `SemanticResultsList`, `QuickActionChips` | `useSemanticSearch()` + `useCommandParser()` |
| Connections Matrix | `IntegrationCard`, `TokenStatusPill` | `useConnections()` → `GET/POST /connections` |

### 2.2 State Management

Given the ambient, always-updating nature of this app (real-time timeline, cross-view freshness), a lightweight global store beats prop drilling or heavy Redux boilerplate:

- **Zustand** for global state (`state/store.ts` composed of slices) — chosen over Redux Toolkit for less ceremony, over Context API because the timeline updates at high frequency and Context re-renders are costly.
- **TanStack Query (React Query)** layered on top of Zustand for server-state: caching, background refetch, and stream reconciliation for `/brief`, `/search`, `/connections`. Zustand owns *client* state (UI toggles, command bar input, filters); React Query owns *server* state.
- **Slices:**
  - `briefSlice`: today's brief, last-refreshed timestamp, loading/error state.
  - `timelineSlice`: append-only ring buffer of events (cap at ~500 in memory, paginate older via API), active filters (source, type, date range).
  - `connectionsSlice`: per-integration status (`connected | expired | error | disconnected`).
  - `uiSlice`: command deck open/closed, active route, toast queue.

### 2.3 API Interaction Hooks (contract)

```ts
// hooks/useMorningBrief.ts
useMorningBrief(): { brief: Brief | null; isLoading: boolean; refresh: () => void }

// hooks/useTimelineStream.ts
useTimelineStream(filters: TimelineFilters): { events: TimelineEvent[]; connected: boolean }
// Implementation: opens EventSource to /api/v1/timeline/stream, dedupes by event.id,
// falls back to polling GET /timeline?since=<cursor> if SSE unsupported/blocked.

// hooks/useSemanticSearch.ts
useSemanticSearch(): { search: (query: string) => Promise<SearchResult[]>; results: SearchResult[]; isSearching: boolean }

// hooks/useCommandParser.ts
useCommandParser(): { submit: (text: string) => Promise<CommandResult> }
// Sends raw NL string to POST /command; backend agent decides tool (create_reminder,
// calendar_tool, etc.) and returns a structured confirmation for the UI to render.

// hooks/useConnections.ts
useConnections(): { connections: Connection[]; connect: (provider) => void; revoke: (id) => void }
```

### 2.4 Real-time transport choice
Server-Sent Events (SSE) over a raw WebSocket for the Timeline Feed: traffic is one-directional (server → client), SSE auto-reconnects natively, and it's simpler to proxy through standard infra (nginx/ALB) than WS. Reserve WebSockets only if you later need bidirectional low-latency features (e.g., live voice command streaming).

---

## 3. Databases & Data Flow Logic

### 3.1 Pinecone Namespace & Metadata Strategy

**Isolation model:** one namespace per `user_id` (hard tenant boundary — never mix users in a shared namespace, even with metadata filters, since a filter bug becomes a cross-tenant data leak). Within a user's namespace, use metadata for sub-partitioning:

```json
{
  "source": "whatsapp" | "gmail" | "gcal" | "manual",
  "document_type": "reminder" | "summary" | "message" | "event",
  "created_at": 1735500000,
  "thread_id": "optional-conversation-grouping",
  "processed": true,
  "ttl_hint": 1738092000
}
```

- **Index config:** single index, dimension matched to `bge-large-en-v1.5` (1024-d), cosine similarity.
- **Chunking:** short messages (WhatsApp/SMS) stored as single vectors; longer content (emails, documents) chunked ~400–600 tokens with 15% overlap via `chunker.py`, each chunk upserted with a shared `parent_id` metadata field so retrieval can be re-assembled or deduplicated at the parent level.
- **Retention:** since this is a personal-memory system, not everything needs to live forever. Use `ttl_hint` plus a scheduled job to prune low-value `document_type: "message"` vectors older than N days, while `summary`/`reminder` types persist longer. This keeps namespace size (and cost) manageable.
- **Hybrid search:** combine Pinecone's dense vector search with metadata filters (`source`, `document_type`, `created_at` range) rather than pure semantic recall — this is what makes "Hybrid Semantic Vector search" in your spec actually hybrid, versus vector-only.

### 3.2 End-to-End Data Flow (WhatsApp message → UI)

1. **Ingress:** WhatsApp Business API (or Twilio) POSTs to `POST /api/v1/webhooks/whatsapp`. FastAPI route validates signature, returns `202 Accepted` immediately, and hands the raw payload to a background task (`BackgroundTasks` or a queue like Redis/Celery for higher volume) — this keeps the webhook non-blocking as required.
2. **Normalize:** `services/ingestion/normalizer.py` converts the provider-specific payload into a canonical `Document` domain object: `{ text, source, external_id, user_id, timestamp, raw_metadata }`.
3. **Chunk (if needed):** `chunker.py` splits long text; short chats pass through untouched.
4. **Embed:** `services/embeddings/hf_embedder.py` calls the Hugging Face model (`bge-large-en-v1.5`) either via local inference pipeline or Hugging Face Inference Endpoints, returning a 1024-d vector per chunk.
5. **Upsert:** `services/vectorstore/pinecone_client.py` writes to the user's namespace with the metadata schema above. `namespace_router.py` resolves `user_id → namespace` (and enforces the isolation boundary).
6. **Event emit:** on successful upsert, `services/realtime/event_bus.py` publishes a lightweight event (`{ id, source, preview, created_at }`) to an in-process pub/sub (or Redis pub/sub if multi-instance).
7. **Push to UI:** the `/timeline/stream` SSE endpoint subscribes to the event bus and forwards new events to any connected client for that `user_id`.
8. **Frontend:** `useTimelineStream` receives the event, appends it to `timelineSlice`, and `TimelineItem` renders it — typically within 1–2 seconds of the original WhatsApp message arriving.
9. **On-demand synthesis (Morning Brief / search):** when the user opens the Dashboard or issues a command, `services/agent/orchestrator.py` (LangChain agent) runs a retrieval query against Pinecone (scoped to that user's namespace, filtered by recency/type), assembles a structured prompt, calls the synthesis LLM, and returns a structured `Brief` or `SearchResult[]` payload via the Pydantic-validated response model.

### 3.3 Why this order matters
Decoupling ingestion (steps 1–6, always-on, cheap) from synthesis (step 9, on-demand, LLM-cost-bearing) means you're not calling an LLM every time a WhatsApp message lands — only when the user actually asks for a brief or searches. This is the difference between a system that's affordable at scale and one that isn't.

---

## 4. Phased Sprint Roadmap

### Phase 0 — Foundations (½ sprint)
- Repo scaffolding per the tree above, CI skeleton, `docker-compose` for local Postgres (credentials) + backend + frontend.
- `pydantic-settings` config loading, `.env.template` finalized.
- Empty FastAPI app with health check; empty Vite app with Tailwind wired.

### Phase 1 — Local Ingestion MVP
- Build one webhook (start with email via SendGrid inbound parse — easiest to test without WhatsApp Business approval).
- Implement `normalizer.py`, `hf_embedder.py`, `pinecone_client.py`, and the upsert pipeline end-to-end.
- Verify: send a test email → confirm vector appears in Pinecone with correct namespace/metadata.
- No UI yet — validated via API tests and a Pinecone console check.

### Phase 2 — Core Memory Layer
- Add WhatsApp and Google Calendar webhook receivers.
- Build `namespace_router.py` isolation logic + multi-user test coverage (critical: write a test that asserts one user's query never returns another user's vectors).
- Implement `search.py` endpoint (`POST /search`) with hybrid metadata filtering.
- Implement retention/TTL pruning job.

### Phase 3 — Agent Orchestration
- Build `services/agent/orchestrator.py` with LangChain `AgentExecutor` and the tool set: `search_memory_tool`, `create_reminder_tool`, `calendar_tool`, `summarize_tool`.
- Wire `POST /command` (natural-language task creation, e.g., "remind me to call Dave when I leave").
- Wire `GET /brief/today` — scheduled or on-demand synthesis using retrieved memory + templated prompt.

### Phase 4 — Dashboard Client Integration
- Build Dashboard, Timeline Feed, Control Deck, Connections Matrix views against the now-functional API.
- Implement SSE `useTimelineStream` with reconnect/backoff and polling fallback.
- Implement Zustand slices + React Query wiring.

### Phase 5 — Connections Matrix & Credential Security
- Build the encrypted credential store (`db/credential_store.py`), OAuth flows for Gmail/GCal, webhook secret rotation for WhatsApp.
- UI: connect/disconnect flows, live status pills, error states (expired token, revoked scope).

### Phase 6 — Hardening & Privacy Pass
- Rate limiting on `/command` and `/search`.
- Namespace-isolation penetration test (attempt cross-tenant retrieval, confirm it's impossible).
- PII scrubbing option before embedding (configurable per source).
- Structured logging + observability (request tracing through ingestion pipeline).
- Load test the ingestion pipeline (webhook burst handling, background task queue depth).

### Phase 7 — Polish & Launch Readiness
- Error boundaries + empty states across all four views.
- Onboarding flow for first-time connection setup.
- Docker production images, deployment scripting, secrets management wired to actual vault/manager (not `.env` in prod).

---

## 5. Core Component Code Template — LangChain Agent Orchestrator

This is a runnable skeleton for `app/services/agent/orchestrator.py`, showing structured tool calling against Pinecone-backed memory. Adapt model/provider names to whatever HF-hosted or Anthropic-compatible endpoint you finalize on.

```python
# app/services/agent/orchestrator.py
"""
LangChain agent orchestrator for Umbra Assistant.
Handles: memory retrieval, reminder creation, calendar queries, and summarization
via structured tool calling.
"""

from typing import Any
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from app.services.vectorstore.pinecone_client import PineconeClient
from app.services.vectorstore.namespace_router import resolve_namespace
from app.services.embeddings.hf_embedder import embed_text
from app.core.config import settings


# ---- Tools -----------------------------------------------------------------

def build_search_memory_tool(user_id: str):
    """Factory: binds the tool to a specific user's isolated namespace."""

    @tool("search_memory")
    def search_memory(query: str, source_filter: str | None = None, top_k: int = 5) -> str:
        """
        Search the user's personal memory (emails, messages, calendar events)
        for content semantically related to the query. Optionally filter by
        source: 'whatsapp', 'gmail', or 'gcal'.
        """
        namespace = resolve_namespace(user_id)
        query_vector = embed_text(query)

        metadata_filter: dict[str, Any] = {}
        if source_filter:
            metadata_filter["source"] = {"$eq": source_filter}

        results = PineconeClient.get_index().query(
            namespace=namespace,
            vector=query_vector,
            top_k=top_k,
            filter=metadata_filter or None,
            include_metadata=True,
        )

        if not results.matches:
            return "No relevant memory found."

        formatted = "\n".join(
            f"- [{m.metadata.get('source')}] {m.metadata.get('text_preview', '')} "
            f"(score={m.score:.2f})"
            for m in results.matches
        )
        return formatted

    return search_memory


@tool("create_reminder")
def create_reminder(task: str, trigger: str) -> str:
    """
    Create a reminder for the user. `trigger` can be a time expression
    ('tomorrow 9am') or a condition ('when I leave the office').
    Returns a confirmation string; actual persistence is handled by the
    calling service layer, not this tool directly.
    """
    # In production: enqueue to a reminders service / write to credential_store-adjacent DB.
    return f"Reminder set: '{task}' (trigger: {trigger})"


@tool("calendar_lookup")
def calendar_lookup(date_range: str) -> str:
    """
    Look up calendar events for a given natural-language date range
    (e.g. 'today', 'this week').
    """
    # Placeholder — in production this calls the GCal service wrapper.
    return f"Calendar lookup stub for range: {date_range}"


# ---- Agent Assembly ---------------------------------------------------------

SYSTEM_PROMPT = """You are Umbra, a private personal-operating-system assistant.
You have access to the user's cross-application memory (emails, messages,
calendar) via tools. Always ground factual claims in tool results — never
invent dates, names, or message content. If memory search returns nothing
relevant, say so plainly rather than guessing.

When asked to create a reminder or task, use the create_reminder tool.
When asked about schedule, use calendar_lookup.
When asked to recall or summarize past information, use search_memory."""


def build_agent_executor(user_id: str) -> AgentExecutor:
    """
    Constructs a per-request agent executor scoped to a specific user's
    memory namespace. Tools are instantiated fresh per call to guarantee
    namespace isolation (never reuse a bound tool across users).
    """
    tools = [
        build_search_memory_tool(user_id),
        create_reminder,
        calendar_lookup,
    ]

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    llm = settings.get_chat_model()  # returns configured LangChain chat model client

    agent = create_tool_calling_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=settings.DEBUG,
        max_iterations=6,
        handle_parsing_errors=True,
    )


async def run_command(user_id: str, command_text: str, chat_history: list | None = None) -> dict:
    """
    Entry point called by app/api/v1/routes/commands.py.
    """
    executor = build_agent_executor(user_id)
    result = await executor.ainvoke({
        "input": command_text,
        "chat_history": chat_history or [],
    })
    return {
        "output": result["output"],
        "intermediate_steps": [
            {"tool": step[0].tool, "input": step[0].tool_input}
            for step in result.get("intermediate_steps", [])
        ],
    }
```

**Notes on this template:**
- Tools are **rebuilt per user request** (`build_search_memory_tool(user_id)`), not module-level singletons — this is the enforcement point for namespace isolation at the agent layer, not just the DB layer.
- `search_memory` returns a formatted string rather than raw vector data, keeping the LLM's context clean and giving it something directly usable for synthesis.
- `handle_parsing_errors=True` and `max_iterations=6` are defensive defaults — agents that can loop indefinitely or crash on malformed tool-call JSON are a real production failure mode worth guarding against from day one.
- `create_reminder` and `calendar_lookup` are stubs — wire them to real service calls in Phase 3 once the reminders/calendar services exist.

---

## Open Questions Worth Resolving Before Phase 1

1. **Synthesis LLM hosting:** "open-source synthesis LLM hosted via Hugging Face" — confirm whether this means HF Inference Endpoints (managed, costs scale with usage) or self-hosted (more ops burden, more control). This affects `settings.get_chat_model()`'s implementation and your cost model.
2. **Background task infra:** `BackgroundTasks` (FastAPI built-in) is fine for MVP but doesn't survive process restarts or scale across multiple backend instances. If you expect webhook volume to grow, plan for Redis/Celery or a lightweight queue (e.g., Arq) from Phase 2 onward rather than retrofitting later.
3. **WhatsApp Business API approval lead time** can be weeks — worth starting that process in parallel with Phase 0/1 rather than blocking on it.

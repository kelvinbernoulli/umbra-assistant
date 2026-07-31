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

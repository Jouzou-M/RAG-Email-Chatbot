# Architecture & User Manual

## System Overview

A production-grade RAG (Retrieval-Augmented Generation) chatbot that indexes your Gmail emails and lets you ask natural language questions about them. Answers include source citations so you can verify every claim.

```
Gmail API ──> Processing Pipeline ──> ChromaDB ──> RAG Pipeline ──> FastAPI ──> Streamlit UI
  (OAuth2)    (parse, chunk)         (vectors)    (retrieve+LLM)    (REST/SSE)   (chat)
```

---

## How to Use It

### Prerequisites
- Python 3.11+
- A Google Cloud project with Gmail API enabled
- OAuth 2.0 credentials (Desktop application type)
- An OpenAI API key (or Anthropic key, or local Ollama)

### Step 1: Install
```bash
cd RAG-Email-Chatbot
pip install -e ".[dev]"
```

### Step 2: Configure
```bash
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-your-key-here
GMAIL_CREDENTIALS_PATH=./credentials.json
```

Place your Google OAuth `credentials.json` in the project root.

### Step 3: Start the API
```bash
make run-api
```
This starts FastAPI on `http://localhost:8000`. On first run, a browser window opens for Gmail OAuth consent.

### Step 4: Start the UI
```bash
make run-ui
```
This starts Streamlit on `http://localhost:8501`.

### Step 5: Sync Your Emails
1. Open `http://localhost:8501`
2. Click **Sync Now** in the sidebar
3. Wait for the sync to complete (check status in sidebar)

### Step 6: Chat
Type a question like:
- "What emails did I get this week?"
- "What did john@company.com say about the budget?"
- "Summarize the emails I sent last month"
- "Are there any emails about the Q3 deadline?"

Answers include source citations with sender, date, and subject.

---

## Architecture Deep Dive

### Module Map

```
src/email_rag/
  config.py                 # All settings from .env (Pydantic)

  gmail/                    # Layer 1: Email Fetching
    auth.py                 #   OAuth2 flow + token refresh
    client.py               #   Gmail API wrapper (list, get, sync)
    models.py               #   Data models (EmailMessage, SyncState)

  processing/               # Layer 2: Email Processing
    parser.py               #   HTML-to-text, signature stripping
    chunker.py              #   Recursive boundary-aware text splitting
    metadata.py             #   Extract ChromaDB-compatible metadata
    thread.py               #   Thread grouping and reconstruction

  embeddings/               # Layer 3: Vector Embedding
    base.py                 #   Abstract interface
    openai.py               #   OpenAI text-embedding-3-small
    sentence_transformer.py #   Local all-MiniLM-L6-v2

  vectorstore/              # Layer 4: Storage
    store.py                #   ChromaDB wrapper (add, search, sync state)
    schema.py               #   Chunk IDs, metadata validation

  rag/                      # Layer 5: Retrieval + Generation
    retriever.py            #   Query parsing, search, dedup, orchestration
    prompt.py               #   System prompt, context formatting
    chain.py                #   LLM streaming (OpenAI/Anthropic/Ollama)
    conversation.py         #   Multi-turn session memory

  api/                      # Layer 6: HTTP API
    app.py                  #   FastAPI factory
    deps.py                 #   Dependency injection (singletons)
    middleware.py            #   CORS, request logging
    schemas.py              #   Request/response models
    routes/chat.py          #   POST /api/chat, /api/chat/stream
    routes/ingest.py        #   POST /api/ingest/sync, /reindex
    routes/health.py        #   GET /health, /health/ready

  ui/                       # Layer 7: Web Interface
    app.py                  #   Streamlit entry point
    state.py                #   Session state initialization
    components/chat.py      #   Chat messages + streaming
    components/sidebar.py   #   Sync controls + filters
```

### Data Flow: Email Sync

```
1. User clicks "Sync Now" in Streamlit sidebar
2. Streamlit POSTs to /api/ingest/sync
3. FastAPI schedules background task _run_sync()
4. _run_sync() loads persisted SyncState from ChromaDB
5. If history_id exists: Gmail History API (incremental, delta only)
   If history expired or first run: Gmail messages.list (full sync)
6. Each message is fetched and parsed:
   - MIME walked for text/plain and text/html parts
   - Base64-decoded body
   - Headers extracted (From, To, Date, Subject, etc.)
   - Attachments identified (metadata only)
7. For each email with a body:
   a. HTML converted to text (BeautifulSoup)
   b. Signatures stripped
   c. Text split into overlapping chunks (512 chars, 64 overlap)
   d. Metadata extracted per chunk (sender, date, labels, etc.)
8. All chunks embedded (OpenAI API or local model)
9. Chunks upserted into ChromaDB (idempotent via message_id_chunkIndex)
10. New SyncState persisted (history_id, timestamp, count)
```

### Data Flow: Chat Query

```
1. User types "What did Sarah say about the budget last week?"
2. Streamlit streams POST to /api/chat/stream
3. EmailRetriever.query_stream() orchestrates:

   a. PARSE FILTERS (regex, no LLM needed):
      - "from sarah" -> sender filter (semantic only, no metadata)
      - "last week" -> date_after/date_before timestamps

   b. SEARCH:
      - Embed the query via OpenAI
      - Query ChromaDB: cosine similarity + metadata filters
      - Cap results to collection size (prevent crash)

   c. DEDUPLICATE:
      - Keep only the best-scoring chunk per email
      - Sort by distance (most relevant first)

   d. FORMAT CONTEXT:
      - Each result becomes:
        [Email 1] From: Sarah | Date: 2024-03-15 | Subject: Q1 Budget
        ---
        <chunk text>
        ---

   e. BUILD MESSAGES:
      - System prompt (citation rules)
      - Previous conversation turns (if multi-turn)
      - Current query + context

   f. STREAM LLM:
      - Send to OpenAI/Anthropic/Ollama
      - Yield tokens as SSE events
      - Record turn in conversation memory

4. Streamlit renders tokens in real-time with cursor
5. Sources shown as expandable cards below the answer
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Chat (returns full response) |
| `POST` | `/api/chat/stream` | Chat (SSE streaming) |
| `GET` | `/api/chat/history/{session_id}` | Get conversation history |
| `DELETE` | `/api/chat/history/{session_id}` | Clear session |
| `POST` | `/api/ingest/sync` | Trigger incremental email sync |
| `POST` | `/api/ingest/reindex` | Full reindex (clear + resync) |
| `GET` | `/api/ingest/status` | Sync status and metrics |
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check (vector store, embeddings, LLM) |

### Chat Request
```json
POST /api/chat/stream
{
  "message": "What emails did I get today?",
  "session_id": "abc123",
  "filters": {"is_sent": false}
}
```

### SSE Stream Events
```
data: {"type": "token", "content": "Based on"}
data: {"type": "token", "content": " your emails"}
data: {"type": "sources", "sources": [{"sender": "...", "date": "...", "subject": "..."}]}
data: {"type": "done"}
```

---

## Configuration Reference

All settings via environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| **Gmail** | | |
| `GMAIL_CREDENTIALS_PATH` | `./credentials.json` | OAuth credentials file |
| `GMAIL_TOKEN_PATH` | `./data/token.json` | Persisted OAuth token |
| `GMAIL_MAX_RESULTS` | `500` | Max emails per sync |
| **Embeddings** | | |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `sentence-transformer` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Model name |
| `EMBEDDING_DIMENSION` | `1536` | Vector dimension |
| `OPENAI_API_KEY` | — | Required for OpenAI provider |
| **LLM** | | |
| `LLM_PROVIDER` | `openai` | `openai`, `anthropic`, or `ollama` |
| `LLM_MODEL` | `gpt-4o-mini` | Model name |
| `LLM_TEMPERATURE` | `0.1` | Lower = more deterministic |
| `LLM_MAX_TOKENS` | `2048` | Max response tokens |
| `ANTHROPIC_API_KEY` | — | Required for Anthropic provider |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| **Vector Store** | | |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB storage path |
| `CHROMA_COLLECTION_NAME` | `emails` | Collection name |
| **RAG** | | |
| `RETRIEVAL_TOP_K` | `10` | Chunks to retrieve per query |
| `CHUNK_SIZE` | `512` | Characters per chunk |
| `CHUNK_OVERLAP` | `64` | Overlap between chunks |
| **API** | | |
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | API port |
| `CORS_ORIGINS` | `["http://localhost:8501"]` | JSON array of allowed origins |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## Docker Deployment

```bash
# Build and start
docker compose up -d

# API: http://localhost:8000
# UI:  http://localhost:8501
```

The compose file:
- Mounts `./data` for persistent ChromaDB storage
- Mounts `./credentials.json` read-only for OAuth
- Sets `API_BASE_URL=http://api:8000` for container-to-container networking
- Reads all config from `.env`

**Important:** Single-worker only. Do not use `--workers N` with N > 1 — the in-memory sync lock is not distributed.

---

## Fully Local Mode (No API Keys)

To run everything locally without sending data to OpenAI:

```env
EMBEDDING_PROVIDER=sentence-transformer
LLM_PROVIDER=ollama
LLM_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
```

1. Install [Ollama](https://ollama.ai) and pull a model: `ollama pull llama3`
2. The sentence-transformer model downloads automatically on first use (~90MB)
3. All email content stays on your machine

---

## Project Structure for Contributors

```
RAG-Email-Chatbot/
  src/email_rag/        # Main package (pip install -e .)
  tests/unit/           # Unit tests (pytest)
  tests/integration/    # Integration tests (need real credentials)
  .env.example          # Configuration template
  pyproject.toml        # PEP 621 project metadata
  Makefile              # Dev commands (test, lint, run-api, run-ui)
  Dockerfile            # Multi-stage build
  docker-compose.yml    # API + UI services
  BUGS_AND_LESSONS.md   # Bug catalog and DOs/DON'Ts
```

### Running Tests
```bash
make test          # Unit tests only (no credentials needed)
make test-all      # All tests including integration
make lint          # Ruff + mypy
make format        # Auto-format
```

### Key Design Decisions

1. **Two-process architecture** (FastAPI + Streamlit) — API is independently testable and deployable; frontend is swappable
2. **ChromaDB** — Zero infrastructure, native metadata filtering, sufficient for personal email (~1M vectors)
3. **Incremental sync** — Gmail History API fetches only new messages, not the entire inbox
4. **Boundary-aware chunking** — Splits on paragraphs > lines > sentences > words, preserving meaning
5. **Implicit filter parsing** — Regex extracts dates and senders from natural language without an extra LLM call
6. **Idempotent upserts** — Re-syncing the same email overwrites, never duplicates
7. **Streaming SSE** — Tokens appear in the UI as the LLM generates them

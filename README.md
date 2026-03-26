# Email RAG Chatbot

Production-grade Retrieval-Augmented Generation chatbot for Gmail emails. Ask natural language questions about your email archive and get accurate, cited answers.

## Architecture

```
Gmail API ──> Processing Pipeline ──> ChromaDB ──> RAG Pipeline ──> FastAPI ──> Streamlit UI
  (OAuth2)    (MIME parse, chunk)    (vectors)    (retrieve+LLM)    (REST)      (chat)
```

**Stack:** Python 3.11+ | ChromaDB | OpenAI/Anthropic/Ollama | FastAPI | Streamlit

## Features

- **Gmail Integration** — OAuth2 authentication, incremental sync via History API
- **Smart Processing** — HTML stripping, MIME parsing, signature removal, recursive chunking
- **Hybrid Search** — Semantic vector search + metadata filtering (sender, date, labels)
- **Configurable LLM** — OpenAI, Anthropic, or Ollama (fully local/private)
- **Streaming Chat** — Real-time token streaming with source citations
- **Multi-turn Memory** — Conversational context across questions
- **Production Ready** — Structured logging, error handling, Docker support, idempotent syncs

## Quick Start

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API keys and Gmail credentials path
```

### 3. Run

```bash
# Terminal 1: Start the API server
make run-api

# Terminal 2: Start the Streamlit UI
make run-ui
```

Open http://localhost:8501 — click "Sync Now" to index your emails, then start chatting.

## Configuration

All configuration via environment variables (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `GMAIL_CREDENTIALS_PATH` | `./credentials.json` | Google OAuth credentials file |
| `EMBEDDING_PROVIDER` | `openai` | `openai` or `sentence-transformer` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model name |
| `LLM_PROVIDER` | `openai` | `openai`, `anthropic`, or `ollama` |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB storage path |
| `RETRIEVAL_TOP_K` | `10` | Number of chunks to retrieve |
| `CHUNK_SIZE` | `512` | Characters per chunk |

## Docker

```bash
docker compose up -d
```

API at http://localhost:8000, UI at http://localhost:8501.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Chat (non-streaming) |
| `POST` | `/api/chat/stream` | Chat (SSE streaming) |
| `POST` | `/api/ingest/sync` | Trigger email sync |
| `GET` | `/api/ingest/status` | Sync status + stats |
| `POST` | `/api/ingest/reindex` | Full reindex |
| `GET` | `/health` | Liveness check |
| `GET` | `/health/ready` | Readiness check |

## Project Structure

```
src/email_rag/
  config.py          # Pydantic Settings (env-based config)
  gmail/             # OAuth2 auth, Gmail API client, incremental sync
  processing/        # MIME parsing, HTML stripping, chunking, metadata
  embeddings/        # OpenAI + sentence-transformers providers
  vectorstore/       # ChromaDB wrapper with hybrid search
  rag/               # Retriever, prompts, LLM chain, conversation memory
  api/               # FastAPI backend (routes, middleware, schemas)
  ui/                # Streamlit frontend (chat, sidebar, state)
tests/
  unit/              # Parser, chunker, retriever, conversation tests
  integration/       # Gmail, vector store, RAG chain tests
```

## Testing

```bash
make test           # Unit tests only
make test-all       # All tests (requires credentials)
make lint           # Ruff + mypy
```

## Gmail Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download `credentials.json` to the project root
5. On first run, complete the browser OAuth consent flow

---

Also includes: [IMDB Sentiment Analysis](IMDB_Ratings_Sentiment_Analysis_NLP_Model.ipynb) — a separate Bidirectional LSTM model for movie review classification.

# Bugs, DOs and DON'Ts

38 bugs were caught and fixed across 5 audit passes before production. This document captures the lessons so they never come back.

---

## Critical Bugs That Were Fixed

### 1. ChromaDB crashes when `n_results` > collection size
- `collection.query(n_results=10)` on a collection with 3 documents raises `NotEnoughElements`
- **Happens on every fresh deployment** — first chat query after first sync always crashes
- **Fix:** Cap `n_results` to `min(top_k, collection.count())` and catch filter-narrowed errors

### 2. `$contains` is not a valid ChromaDB `where` operator
- ChromaDB metadata filters only support: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`
- Using `$contains` in a `where` clause crashes at runtime — no substring matching exists
- **Fix:** Use exact match or let semantic search handle partial matches

### 3. Sync Gmail calls block the async event loop
- `GmailClient.sync_messages()` is synchronous — calling it inside `async def` freezes the entire FastAPI server
- **Fix:** Wrap in `asyncio.to_thread()`

### 4. Silent data loss on expired Gmail History ID
- `_incremental_sync` caught the 404 error, logged "falling back to full sync", but returned `[]`
- The caller treated `[]` as "zero new messages" — **never actually performed the full sync**
- All emails since the last sync were permanently missed
- **Fix:** Return `None` to signal expiry; caller checks and falls back to actual full sync

### 5. Sender regex captures time words
- "emails from this week" → `sender="this"`, "from last month" → `sender="last"`
- Combined with date filters, the bogus sender filter returns zero results
- **Fix:** Exclude known time words ("this", "last", "today", "yesterday") from sender capture

### 6. Ollama streaming was completely broken
- Used `await client.post()` which waits for the full response before returning
- Streaming requires `async with client.stream("POST", ...)` context manager
- **Fix:** Rewrote to use proper HTTP streaming

### 7. Sidebar date filters were dead controls
- "Today", "This week", "This month", "Last month" dropdown options did absolutely nothing
- Only "Custom" had handler code — the other 4 options were silently ignored
- **Fix:** Implemented all date filter handlers

### 8. Double-click fires two concurrent syncs
- Race window between checking `_syncing` flag and background task starting
- Two syncs running simultaneously corrupt ChromaDB and produce wrong sync state
- **Fix:** Set `_syncing = True` in the endpoint handler before scheduling the task

---

## DOs

### Architecture
- **DO** use `asyncio.to_thread()` for any synchronous blocking I/O in async functions (Gmail API, CPU-bound embeddings)
- **DO** cap ChromaDB `n_results` to collection count before querying
- **DO** use `is not None` instead of `or` when 0 is a valid parameter value (chunk_overlap, max_tokens, temperature)
- **DO** validate and constrain user-facing inputs (session_id, message length, filters)
- **DO** set locks/flags BEFORE scheduling background tasks, not inside them
- **DO** use module-level constants for values computed in hot paths (`_DATETIME_MIN_UTC`)
- **DO** use lazy client initialization for LLM/embedding providers (only create when first needed)
- **DO** flatten nested `$and` conditions when combining multiple filter sources
- **DO** return generic error messages to clients, log the real exception server-side

### ChromaDB
- **DO** use `upsert` (not `add`) for idempotent operations
- **DO** store timestamps as floats for range queries (`$gte`, `$lte`)
- **DO** JSON-encode lists before storing as metadata (ChromaDB only supports primitives)
- **DO** use cosine similarity (`{"hnsw:space": "cosine"}`) for text embeddings
- **DO** handle empty collections gracefully before any query

### Gmail
- **DO** use the History API for incremental sync (not polling `messages.list`)
- **DO** handle history expiration by falling back to full sync
- **DO** deduplicate message IDs during incremental sync (history can return duplicates)
- **DO** use `urlsafe_b64decode` for Gmail body data (not standard base64)

### RAG
- **DO** deduplicate search results by email (keep only the best-scoring chunk per message)
- **DO** include citation instructions in the system prompt
- **DO** always record an assistant response (even on error) to prevent dangling user turns
- **DO** limit conversation memory (per-turn cap + per-session cap + session eviction)

### Streamlit
- **DO** persist flash messages in `st.session_state` so they survive `st.rerun()`
- **DO** call `st.rerun()` outside of column/container context managers
- **DO** make `api_base` configurable via environment variable for Docker deployments

---

## DON'Ts

### Architecture
- **DON'T** use `value or default` for numeric parameters — `0 or 64` silently becomes `64`
- **DON'T** call synchronous blocking functions inside `async def` without `asyncio.to_thread()`
- **DON'T** create new API clients on every request — cache them (LLM, embedding, Gmail)
- **DON'T** pass empty strings as API keys — pass `None` to let the SDK fall back to env vars
- **DON'T** leak exception details to clients via SSE or HTTP responses
- **DON'T** use module-level `__import__()` hacks inside lambdas
- **DON'T** use mutable default arguments without `Field(default_factory=...)`

### ChromaDB
- **DON'T** use `$contains` in `where` clauses — it doesn't exist for metadata filtering
- **DON'T** query with `n_results` larger than the collection size
- **DON'T** assume filters won't narrow results below `n_results`
- **DON'T** store `None` in metadata — ChromaDB rejects it; use empty string instead
- **DON'T** overwrite the filter dict when combining multiple conditions — use a list then merge

### Gmail
- **DON'T** log "falling back to full sync" without actually doing the full sync
- **DON'T** assume History API always works — it expires after ~7 days of inactivity
- **DON'T** commit `credentials.json` or `token.json` to git

### RAG
- **DON'T** apply metadata filters for name-only sender queries — ChromaDB can't do substring matching, so "from sarah" should rely on semantic search
- **DON'T** capture time-related words as sender names ("from this week" != sender="this")
- **DON'T** let a single long email dominate results — deduplicate by message ID

### Streamlit
- **DON'T** call `st.rerun()` inside `with st.columns()` context — raises `RerunException` before context cleanup
- **DON'T** use `st.sidebar.info()` immediately before `st.rerun()` — the message vanishes
- **DON'T** assume `date_input()` returns None by default — it returns today's date unless `value=None`

### Deployment
- **DON'T** use `localhost` in Docker container-to-container communication — use service names
- **DON'T** run multiple uvicorn workers without replacing the in-memory sync lock
- **DON'T** add unused dependencies to `pyproject.toml`
- **DON'T** forget to document `CORS_ORIGINS` in `.env.example` for deployments behind reverse proxies

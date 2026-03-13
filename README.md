# 🧠 MindVault
### Enterprise Knowledge Base — Hybrid BM25 + PageIndex RAG


[![CI](https://github.com/anamgithub595/MindVault-Hybrid-BM25-PageIndex-RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/anamgithub595/MindVault-Hybrid-BM25-PageIndex-RAG/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A production ready vectorless RAG system for querying organisational documents using
**two complementary retrieval strategies fused via Reciprocal Rank Fusion (RRF)** get cited answers grounded in your documents — not hallucinations:

| Layer | Technology | What it does |
|---|---|---|
| **BM25** | Local SQLite + inverted index | Exact keyword match, <10ms, no GPU |
| **PageIndex** | Cloud API (pageindex.ai) | Tree-based agentic reasoning, semantic understanding |
| **Fusion** | RRF (Reciprocal Rank Fusion) | Combines both signals, alpha-weighted |
| **Generation** | Anthropic Claude / OpenAI GPT | Cited answer with page provenance |
 
---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  INGESTION PIPELINE                                                 │
│                                                                     │
│  Upload PDF/MD/TXT                                                  │
│       │                                                             │
│       ├──▶ Connector (PDFConnector / MarkdownConnector)            │
│       │         │                                                   │
│       │         ▼                                                   │
│       ├──▶ [BM25 PATH]  IndexWriter ──▶ SQLite (page_index table)  │
│       │                                                             │
│       └──▶ [PageIndex PATH]  PageIndexAPIClient                    │
│                 ├── submit_document(pdf_bytes)                      │
│                 └── poll_until_ready()  [background task]          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  QUERY PIPELINE                                                     │
│                                                                     │
│  POST /query {"query": "What is our vacation policy?"}             │
│       │                                                             │
│       ├──▶ BM25Retriever ──────▶ SQLite lookup ──▶ BM25Hits       │
│       │       (parallel)                                           │
│       └──▶ PageIndexRetriever ─▶ PageIndex API ──▶ PINodes        │
│                                                                     │
│       ──▶ HybridRetriever (RRF fusion, alpha=0.5)                 │
│                   │                                                 │
│                   ▼                                                 │
│       ──▶ PromptBuilder (top-K pages + PI excerpts)               │
│                   │                                                 │
│                   ▼                                                 │
│       ──▶ LLMClient (Gemini / Claude / GPT)                                │
│                   │                                                 │
│                   ▼                                                 │
│       ──▶ CitationFormatter ──▶ JSON response with sources        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
mindvault/
├── app/
│   ├── main.py                      # FastAPI app factory
│   ├── api/routes/
│   │   ├── ingest.py                # POST /ingest/upload, /ingest/notion
│   │   ├── query.py                 # POST /query
│   │   └── documents.py             # GET/DELETE /documents, /health
│   ├── core/
│   │   ├── config.py                # Settings (env-driven, cached singleton)
│   │   ├── dependencies.py          # FastAPI Depends() providers
│   │   └── exceptions.py            # All domain exceptions
│   ├── db/
│   │   ├── database.py              # Async SQLAlchemy engine
│   │   ├── models.py                # ORM: documents, pages, page_index, query_log
│   │   └── repositories/
│   │       ├── document_repo.py     # CRUD for documents + pages
│   │       ├── index_repo.py        # BM25 inverted index read/write
│   │       └── query_log_repo.py    # Audit log writer
│   ├── connectors/
│   │   ├── base.py                  # Abstract BaseConnector + RawPage/RawDocument
│   │   ├── pdf_connector.py         # pdfplumber → RawPages
│   │   ├── markdown_connector.py    # Heading-split → RawPages
│   │   └── notion_connector.py      # Notion API → RawPages
│   ├── indexing/
│   │   ├── tokeniser.py             # Text → tokens (no DB, no BM25 math)
│   │   ├── bm25.py                  # Pure BM25 math (no I/O)
│   │   └── index_writer.py          # Orchestrates: RawDoc → SQLite index
│   ├── pageindex/
│   │   └── client.py                # PageIndex API wrapper (submit/poll/retrieve/chat)
│   ├── retrieval/
│   │   ├── bm25_retriever.py        # query → BM25Hits (uses DB)
│   │   ├── pageindex_retriever.py   # query → PINodes (uses PageIndex API)
│   │   └── hybrid_retriever.py      # RRF fusion of both → HybridHits
│   ├── generation/
│   │   ├── llm_client.py            # Anthropic/OpenAI behind one interface
│   │   ├── prompt_builder.py        # Assembles system + user prompt
│   │   └── citation_formatter.py    # Wraps answer with structured sources
│   └── schemas/
│       ├── query.py                 # QueryRequest / QueryResponse
│       └── document.py              # IngestResponse / DocumentSummary / etc.
├── tests/
│   └── unit/
│       ├── test_bm25.py
│       ├── test_hybrid_fusion.py
│       └── test_connectors.py
├── scripts/
│   ├── init_db.py                   # One-shot DB table creation
│   └── smoke_test.py                # End-to-end test (mocked external APIs)
├── config/
│   └── .env.example                 # All environment variables documented
├── requirements.txt
└── pytest.ini
```

---
 
## 🖥️ UI
 
MindVault ships with a built-in dark-theme web interface. Open `http://localhost:8000` after starting the server.
 
Features:
- Document upload with drag-and-drop modal
- Live index stats — documents, pages, BM25 terms (auto-refreshes every 15s)
- Query input with BM25 / Hybrid / Semantic mode switcher
- Answers with inline markdown + citation chips `[Doc: "...", Page N]`
- Source strip showing page number + RRF score per result
- 6 pre-built suggestion queries to click and run instantly
- Toast notifications for upload success/failure
 
---

## ⚙️ Local Setup
 
### Step 1 — Get API Keys
 
| Key | Where | Required? |
|---|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Yes — free tier, 15 RPM |
| `PAGEINDEX_API_KEY` | [dash.pageindex.ai/api-keys](https://dash.pageindex.ai/api-keys) | Optional (BM25 works alone) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | Only if using Claude |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) | Only if using GPT |
 
### Step 2 — Create virtual environment
 
```bash
cd mindvault/
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
```
 
### Step 3 — Install dependencies
 
```bash
pip install -r requirements.txt
```
 
### Step 4 — Configure environment
 
```bash
cp config/.env.example config/.env
```
 
Open `config/.env` and set at minimum:
 
```env
GEMINI_API_KEY=AIza...your-actual-key
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
PAGEINDEX_API_KEY=pi-your-key-here
```
 
### Step 5 — Initialise database
 
```bash
python scripts/init_db.py
```
 
### Step 6 — Start server
 
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
 
Open **http://localhost:8000** for the UI · **http://localhost:8000/docs** for Swagger.
 
### Step 7 — Upload a document
 
Via UI: click **Upload Doc** in the header, drag your PDF in.
 
Via curl:
```bash
curl -X POST http://localhost:8000/ingest/upload \
  -F "file=@/path/to/document.pdf"
```
 
### Step 8 — Query
 
Via UI: type in the query box, press Enter.
 
Via curl:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Who should lead the new data science project?"}'
```
 
Advanced options:
```json
{
  "query": "your question",
  "alpha": 0.5,
  "top_k": 5,
  "doc_ids": [1]
}
```
 
### Step 9 — Run tests
 
```bash
pytest tests/unit/ -v          # 16 unit tests, ~0.5s, no external APIs
python scripts/smoke_test.py   # end-to-end with mocked APIs
```
 
---
 
## 🤖 LLM Providers
 
| Provider | Model | Cost | How to enable |
|---|---|---|---|
| **Google Gemini** | `gemini-2.5-flash` | **Free** (15 RPM) | `LLM_PROVIDER=gemini` |
| Anthropic Claude | `claude-sonnet-4-6` | Prepaid credits | `LLM_PROVIDER=anthropic` |
| OpenAI | `gpt-4o` | Prepaid credits | `LLM_PROVIDER=openai` |
 
Switch provider by changing two lines in `config/.env` — zero code changes needed.
 
---
 
## 🐳 Docker
 
```bash
# Build
docker build -t mindvault:latest .
 
# Run (single container)
docker run -p 8000:8000 --env-file config/.env mindvault:latest
 
# Full stack with Nginx
docker compose up --build -d
docker compose logs -f app
docker compose down
```
 
---
 
## 🚀 Deploy to Railway 
 
1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → select `mindvault`
3. Railway detects the Dockerfile automatically and starts building
4. Go to your service → **Variables** tab, add these 10 variables:
 
| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | your actual Gemini key |
| `PAGEINDEX_API_KEY` | your PageIndex key |
| `LLM_PROVIDER` | `gemini` |
| `LLM_MODEL` | `gemini-2.5-flash` |
| `APP_ENV` | `production` |
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `sqlite+aiosqlite:////app/data/mindvault.db` |
| `HYBRID_ALPHA` | `0.5` |
| `FINAL_TOP_K` | `5` |
| `MAX_UPLOAD_SIZE_MB` | `50` |
 
5. Add a **Volume** mounted at `/app/data` to persist SQLite across deploys
6. Your app is live at `https://your-app.up.railway.app`
 
Every `git push` to `main` triggers an automatic redeploy.
 
---
 
## 🧩 How RRF Fusion Works
 
```
BM25 ranking:     Page A=1st  Page B=2nd  Page C=5th
PageIndex result: Page C=1st  Page A=3rd  Page D=2nd
 
Score formula:  (1-α) × 1/(60+bm25_rank) + α × 1/(60+pi_rank)
 
Pages in BOTH lists get a significant combined boost.
alpha=0.0 = pure BM25 (fast, keyword-exact)
alpha=0.5 = hybrid (default, balanced)
alpha=1.0 = pure PageIndex (semantic, slower)
```
 
---

## 🧩 How Hybrid Fusion Works

```
BM25 ranking:     Page A=1st,  Page B=2nd,  Page C=5th
PageIndex result: Page C=1st,  Page A=3rd,  Page D=2nd

RRF scores (k=60):
  Page A: (1-α)·1/(60+1) + α·1/(60+3)  ← appears in both
  Page B: (1-α)·1/(60+2) + α·0          ← BM25 only
  Page C: (1-α)·1/(60+5) + α·1/(60+1)  ← appears in both
  Page D: (1-α)·0        + α·1/(60+2)  ← PageIndex only

Pages appearing in BOTH lists get a significant score boost.
alpha=0.5 weights both sources equally.
```

---

## 📡 API Reference
 
| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `POST` | `/ingest/upload` | Upload file (PDF / MD / TXT) |
| `POST` | `/ingest/notion` | Ingest Notion page |
| `POST` | `/query` | Hybrid RAG query → cited answer |
| `GET` | `/documents` | List all documents |
| `GET` | `/documents/{id}` | Document detail + status |
| `DELETE` | `/documents/{id}` | Delete document |
| `GET` | `/documents/index/stats` | Index statistics |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |
 
---
 
## 🔧 Customisation
 
**Switch LLM:**
```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
```
 
**Tune BM25:**
```env
BM25_K1=1.5    # term frequency saturation
BM25_B=0.75    # length normalisation
```
 
**Add a new connector (e.g. Confluence):**
1. Create `app/connectors/confluence_connector.py` extending `BaseConnector`
2. Implement `async def extract(source, filename) → RawDocument`
3. Register in `_CONNECTOR_MAP` in `app/ingestion/pipeline.py`
 
**Switch to PostgreSQL:**
```env
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mindvault
```
 
---
 
## Known Limitations
 
- SQLite is single-writer — switch to PostgreSQL for high concurrency
- PageIndex free tier has limited credits — BM25-only mode works fine without it
- Gemini free tier: 15 RPM, ~1000 requests/day — sufficient for demos
- Max file upload: 50MB (configurable via `MAX_UPLOAD_SIZE_MB`)
 
---
 
*Built with FastAPI · SQLite · BM25 · PageIndex · Google Gemini · Docker · Railway*

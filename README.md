# Spectrum RAG — A Production-Grade, Multi-Domain Retrieval-Augmented Generation Platform

> One RAG engine, six grounded knowledge assistants. Hybrid retrieval (dense + BM25 + RRF), cross-encoder reranking, strict citation grounding, refusal & safety guardrails, golden-dataset evaluation — all running on a **single Raspberry Pi** with **zero GPU at query time**.

A configuration-driven RAG platform that answers questions strictly from a curated corpus and **cites every claim back to a source**. Adding a new domain is a matter of dropping a folder — no changes to the core engine. The flagship demo, **Vidhi**, answers questions on Indian law from the freshly-enacted 2023 criminal codes (BNS / BNSS / BSA), the Constitution, and key civil statutes — and refuses to answer (or flags repealed law) when the corpus doesn't support a confident, cited response.

---

## Table of contents

- [Why this project](#why-this-project)
- [The six demos](#the-six-demos)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Retrieval pipeline](#retrieval-pipeline)
- [Key features](#key-features)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Adding a new demo](#adding-a-new-demo)
- [Evaluation](#evaluation)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [Companion docs](#companion-docs)

---

## Why this project

Most RAG demos stop at "embed some PDFs and call an LLM." This one is built like a product:

- **Grounded or silent.** The model is instructed to cite only retrieved `section_ref`s and to **refuse** when context is insufficient — no hallucinated statute numbers. A repealed-law guard catches questions that reference superseded acts (e.g. the old IPC) and points to the current provision.
- **Hybrid retrieval that's actually measured.** Dense (pgvector/HNSW) and lexical (ParadeDB BM25) are fused with Reciprocal Rank Fusion, then re-ranked by a cross-encoder. Four retrieval modes (`hybrid`, `vanilla`, `bm25`, `hyde`) are switchable per request, so retrieval quality can be ablated rather than assumed.
- **Multi-domain by design.** The same engine serves law, education, health, insurance, customer support, and French-language study help. A demo is pure configuration: a manifest, a corpus, prompts, validation checks, and a UI config.
- **Evaluation is first-class.** Every demo ships a **golden dataset** (category-tagged questions with expected citations and machine-checkable assertions), a substring-asserting **section validation oracle** that runs before/after ingest, and a deterministic **LLM-judge / HITL calibration benchmark** (labeled decision-boundary set + TryEval-uploadable run/calibration sets + a judge-vs-gold scorer).
- **Runs cheap.** The production target is a Raspberry Pi 4: ParadeDB in Docker, FastAPI and Next.js bare-metal, models served via API (OpenRouter) so there's **no GPU and no local model load at query time**.

---

## The six demos

Each demo is a self-contained folder under `demos/`. They share one engine, one schema, and one evaluation harness — only their corpus, section grammar, prompts, and guardrails differ.

| Demo | Name | Corpus | Notable challenge |
|------|------|--------|-------------------|
| `law` | **Vidhi** | Indian statutes — BNS 2023, BNSS 2023, BSA 2023, Constitution, Contract Act 1872, Consumer Protection Act 2019, DPDP 2023 | Section/Article grammar, cross-references, **repealed-law (old→new) guard** |
| `education` | **Padhai** | NCERT Class 10 Social Science (History, Geography, Civics, Economics) | Pedagogical structure (numbered headings, Activities, Boxes) |
| `health` | **Vaidya** | WHO disease fact sheets (Diabetes, TB, Malaria, Dengue, Hypertension, Anaemia, Mental Health, COVID-19) | Topical-heading segmentation; strict "not medical advice" framing |
| `insurance` | **Beema** | IRDAI standard policy wordings (Arogya Sanjeevani, Saral Jeevan Bima, Saral Suraksha Bima) | Clause/definition/exclusion structure, tables |
| `support` | **Acme Tasks** | Synthetic SaaS help center, internal policies, release notes, competitor battlecards | **Document-level access control** (public / internal / confidential) |
| `french` | **Bonjour** | Multi-board French study material (CBSE, IB) | Multilingual retrieval; `fr` / `en` / `bilingual` answer modes |

---

## Tech stack

**Backend (API)**
- **Python 3.11+**, **FastAPI**, **Uvicorn** — async HTTP API
- **Pydantic v2** + **pydantic-settings** — typed models & config
- **psycopg 3** with async connection pooling

**Vector + lexical search**
- **ParadeDB** (PostgreSQL) — a single database providing both:
  - **pgvector** with an **HNSW** index (cosine) for dense retrieval
  - **`pg_search`** (BM25, Tantivy-backed) for lexical retrieval, with filter predicates fused into the index walk

**Models (served via API — no local weights in production)**
- **Embeddings:** `BAAI/bge-m3` (1024-dim, multilingual) via OpenRouter; local `Qwen/Qwen3-Embedding-0.6B` fallback (sentence-transformers + PyTorch, MPS/CUDA/CPU) for offline dev
- **Generation:** **Claude Sonnet 4.5** (via OpenRouter)
- **HyDE & query condensing:** GPT-4.1-mini (fast/cheap slot)
- **Reranking:** cross-encoder via OpenRouter rerank API (NVIDIA Llama-Nemotron-Rerank, or Cohere `rerank-v3.5`)
- **LLM gateway:** OpenRouter, with optional **Cloudflare AI Gateway** for caching/observability

**Ingestion**
- **marker-pdf** (PDF → clean Markdown/text), **pypdf**, **tiktoken** (token-accurate chunking)
- Manifest-driven section segmentation + per-demo ingest hooks

**Frontend (Web)**
- **Next.js 16**, **React 19**, **TypeScript**, **Tailwind CSS v4**
- **react-markdown** + **remark-gfm**; **pnpm**

**Infrastructure**
- **Docker Compose** (database), **systemd** services, **Raspberry Pi** (ARM64) target
- **Cloudflare Tunnel** for public ingress
- Bring-your-own-key (`X-OpenRouter-Key` header) with optional server-side key fallback

---

## Architecture

```
                          ┌──────────────────────────────────────────────────┐
   PDF / TXT / MD         │                  INGEST (offline)                 │
   corpus  ──────────────▶│  marker-pdf → clean text                          │
                          │  → manifest regex section segmentation            │
                          │  → 512-token sub-chunks (64 overlap, tiktoken)    │
                          │  → bge-m3 embeddings (1024-dim)                    │
                          │  → INSERT into Postgres `chunks`                   │
                          └───────────────────────────┬──────────────────────┘
                                                       │
                              ┌────────────────────────▼────────────────────────┐
                              │   ParadeDB (PostgreSQL)                          │
                              │   chunks(content, embedding vector(1024),        │
                              │          section_ref, doc_title, visibility, …)  │
                              │   • HNSW index  (pgvector, cosine)               │
                              │   • BM25 index  (pg_search)                      │
                              └────────────────────────▲────────────────────────┘
                                                       │
   Browser (Next.js)                                   │
        │  question + history                          │
        ▼                                              │
   POST /api/{demo}/query                              │
        │                                              │
        ▼                                              │
   ┌──────────────────────────────────────────────────┴──────────────────────┐
   │                           QUERY (online, per request)                     │
   │  1. Condense follow-up → standalone query (multi-turn)                    │
   │  2. (optional) HyDE: draft hypothetical answer → embed it                 │
   │  3. Embed query (bge-m3, asymmetric query prefix)                         │
   │  4. Retrieve: dense kNN  ⊕  BM25   →  RRF fusion (K=60)   → top_k=20       │
   │  5. Rerank (cross-encoder)                               → top_n=5        │
   │  6. Generate (Claude Sonnet 4.5) with system prompt + cited context       │
   │  7. Return: answer + citations + retrieved chunks + latency/usage trace   │
   └───────────────────────────────────────────────────────────────────────────┘
```

Every query is **scoped to a single `demo_id`** — there is zero cross-demo leakage — and to a **visibility set** (`public` by default), enforced inside both the dense and BM25 SQL.

---

## Retrieval pipeline

| Stage | What happens | Where |
|-------|--------------|-------|
| **Condense** | A follow-up is rewritten into a standalone query using only prior turns (domain-blind). | `app/condense.py` |
| **HyDE** *(optional mode)* | An LLM drafts a hypothetical answer; that text is embedded instead of the raw query. | `app/retrieval.py` |
| **Embed** | `bge-m3` via OpenRouter. Query/passage asymmetry comes from a manual query prefix (OpenRouter ignores `input_type` for bge-m3 — documented and tested). | `app/embed.py` |
| **Dense** | `embedding <=> query_vec` kNN over the HNSW index, filtered by `demo_id` + `visibility`. | `app/retrieval.py` |
| **BM25** | ParadeDB `content @@@ query`, same filters fused into the index walk. | `app/retrieval.py` |
| **Fusion** | Reciprocal Rank Fusion, `score = Σ 1/(K + rank)`, `K = 60`. No score normalization needed. | `app/retrieval.py` |
| **Rerank** | Cross-encoder re-scores the top 20 candidates, keeps top 5. | `app/rerank.py` |
| **Generate** | Claude Sonnet 4.5, per-demo system prompt, context labelled `[section_ref — doc_title]`. | `app/query.py` |

The response includes a full **trace**: per-stage latency (`condense_ms`, `retrieve_ms`, `rerank_ms`, `generate_ms`), token usage, the retrieved chunks with scores, the assembled citations, and a `trace_id`.

---

## Key features

- **Config-driven multi-tenancy.** A demo = `manifest.yaml` + `corpus/` + `prompts/` + `validate_checks.yaml` + `web_config.ts`. The engine discovers demos at runtime (`GET /api/demos`).
- **Four switchable retrieval modes** — `hybrid` (default), `vanilla` (dense), `bm25`, `hyde` — selectable per request for ablation and evaluation.
- **Strict citation grounding** — the model may only cite `section_ref`s present in the retrieved context; section numbers are never recalled from training data.
- **Refusal guardrail** — a canonical "insufficient context" refusal, detected by the UI to render an honest banner instead of a fabricated answer.
- **Repealed-law guard (legal)** — questions referencing superseded statutes (IPC, CrPC, Indian Evidence Act, CP Act 1986) are matched against a `LAW_MAPPINGS` crosswalk and routed to the current provision.
- **Document-level access control** — `public` / `internal` / `confidential` visibility per document, enforced in SQL (demonstrated by the support demo's internal policies & competitor battlecards).
- **Bring-your-own-key** — clients pass `X-OpenRouter-Key`; the server falls back to its own key so the app works out-of-the-box.
- **Observability** — per-stage latency, token usage, and a trace id on every response.
- **Multilingual** — `bge-m3` embeddings + a French demo with `fr` / `en` / `bilingual` answer modes.
- **Golden-dataset evaluation** — category-tagged eval sets, a substring section-validation oracle, and an in-app dataset viewer with a **version picker** (Golden / TryEval Live / TryEval Calibration) plus a **TryEval** export.
- **LLM-judge / HITL benchmark** — per-domain, deterministic (seed 1234) judge datasets with a baked-in 30% failure rate and an ~18% borderline band, graded on Task / Format / Factuality rubrics (support adds Confidentiality / Escalation / Tone), plus a scorer reporting Cohen's κ, fail-class P/R, and borderline flip-rate. Gold labels never reach the model or the judge (packed into `eval_context`, no `${CONTEXT}` in the endpoint template).
- **Premium UI** — dark/light themes, mobile-responsive, a retrieved-chunks inspector, a live corpus viewer, and a settings panel.

---

## Repository layout

```
.
├── apps/
│   ├── api/                     # FastAPI service
│   │   ├── app/
│   │   │   ├── main.py          # app, CORS, /demos, /corpus routes, lifespan
│   │   │   ├── query.py         # /api/{demo}/query — orchestrates the pipeline
│   │   │   ├── retrieval.py     # vanilla / bm25 / hybrid(RRF) / hyde
│   │   │   ├── rerank.py        # cross-encoder rerank via OpenRouter
│   │   │   ├── embed.py         # bge-m3 (OpenRouter) + local qwen3 fallback
│   │   │   ├── condense.py      # multi-turn query condenser
│   │   │   ├── dataset.py       # serves golden + judge datasets (?version=) to the UI
│   │   │   ├── gateway.py       # OpenRouter / Cloudflare AI Gateway client
│   │   │   ├── config.py / db.py
│   │   │   └── prompts/         # engine-level prompts (condense)
│   │   └── scripts/
│   │       ├── ingest.py            # load → segment → sub-chunk → embed → store
│   │       ├── validate_sections.py # substring-asserting section oracle
│   │       ├── init.sql             # schema + HNSW + BM25 indexes
│   │       └── check_pg_search_fusion.sh
│   └── web/                     # Next.js 16 + React 19 + Tailwind v4
│       ├── app/[demo]/page.tsx  # dynamic per-demo chat UI
│       ├── app/components/      # ChunksPanel, CorpusModal, DatasetModal, …
│       └── lib/                 # api client, demo config loader, types
├── demos/                       # one folder per demo (config + corpus + prompts)
│   ├── law/ education/ health/ insurance/ support/ french/
├── golden_sets/                 # evaluation sets + LLM-judge benchmark
│   ├── <demo>-dataset.csv           # golden eval set (per demo)
│   ├── _build_<demo>_judge.py       # deterministic judge-benchmark generator
│   ├── _score_<demo>_judge.py       # judge-vs-gold scorer (κ, P/R, flip-rate)
│   ├── <demo>-judge-dataset.csv     # labeled gold side-file (scores/verdict)
│   ├── <demo>-tryeval-{live,calibration}-dataset.csv   # TryEval uploads
│   ├── <demo>-metrics.json          # TryEval rubric metric definitions
│   └── <demo>-tryeval-setup.md      # per-domain import/calibration guide
├── corpus/                      # shared/raw legal corpus (PDF + clean text)
├── docker-compose.yml           # ParadeDB (+ optional api/web images)
├── DEPLOY.md / ROLLBACK.md      # Raspberry Pi runbook
└── README.md
```

---

## Quick start

### Prerequisites
- Docker (for ParadeDB)
- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)
- Node 20+ and `pnpm`
- An [OpenRouter](https://openrouter.ai) API key

### 1. Configure environment

```bash
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY=sk-or-...
```

### 2. Start the database

```bash
docker compose up db -d
# ParadeDB listens on localhost:5435; init.sql creates the schema + indexes
```

### 3. Ingest a demo corpus

```bash
cd apps/api
uv venv && uv pip install -e .
uv run python -m scripts.ingest --demo law
# validate that section refs resolve to the right content:
uv run python -m scripts.validate_sections --demo law --source db
```

### 4. Run the API

```bash
# from apps/api
uv run uvicorn app.main:app --reload --port 8000
curl localhost:8000/api/health        # {"status":"ok"}
```

### 5. Run the web app

```bash
cd apps/web
pnpm install
pnpm dev            # http://localhost:3002
```

### Try the API directly

```bash
curl -s -X POST 'http://localhost:8000/api/law/query?mode=hybrid' \
  -H 'Content-Type: application/json' \
  -H "X-OpenRouter-Key: $OPENROUTER_API_KEY" \
  -d '{"q":"What is the punishment for murder under BNS 2023?"}' | jq
```

You'll get a cited answer cross-referencing **BNS s.103**, the retrieved chunks with scores, and a latency/usage trace.

---

## Adding a new demo

No engine code changes required:

```
demos/<id>/
├── manifest.yaml         # title, doc titles/shorts, section regex grammar,
│                         #   citation format, refusal/guard markers, visibility
├── corpus/
│   ├── raw/              # source PDFs
│   └── clean/            # marker-pdf output (txt/md), ingested
├── prompts/
│   ├── system_v1.md      # grounded system prompt (uses {context})
│   └── hyde.txt          # HyDE template
├── ingest_hooks.py       # optional per-doc text normalizers
├── validate_checks.yaml  # substring section-validation oracle
└── web_config.ts         # UI: colors, suggested questions, banners
```

Then: `uv run python -m scripts.ingest --demo <id>` and the demo appears automatically in the picker.

---

## Evaluation

Every demo ships a **golden dataset** at `golden_sets/<demo>-dataset.csv` with category-tagged cases:

| Column | Purpose |
|--------|---------|
| `eval_context` | `retrieval` \| `refusal` \| `guard` \| `edge` — filter eval runs by category |
| `input` | the question sent to `/api/{demo}/query` |
| `expected_answer` | reference answer for an LLM-judge comparison |
| `expected_citations` | `section_ref`s that **must** appear in `citations[]` (pipe-separated) |
| `expected_assertions` | machine-checkable flags — `must_cite=…;must_contain=…;should_refuse=…` |

Two complementary checks:

- **Section validation oracle** (`validate_sections.py`) — asserts that each `section_ref` resolves to content containing an expected substring (e.g. *BNS s.103 → "murder"*). Runs against the clean files (pre-ingest) or the DB (post-ingest), and exits non-zero on failure — usable as a CI gate.
- **Golden-set grading** — programmatic citation/assertion checks plus an optional LLM-judge over `expected_answer`. Cases tagged `refusal`/`guard` verify that the model **declines** or **flags repealed law** correctly.

The web app exposes both: a **dataset viewer** (`DatasetModal`, with a Golden / TryEval Live / TryEval Calibration version picker) and a **TryEval export** (`TryEvalExportModal`) for running the set in your own harness.

### LLM-judge / HITL benchmark

Beyond the golden set, every demo ships a **deterministic judge benchmark** for calibrating an LLM-as-judge (or a human-in-the-loop reviewer) before you trust it on a live run. It is generated offline (`_build_<demo>_judge.py`, seed 1234 — no API calls) and is engineered to be a *decision-boundary* set rather than a bimodal one:

- **200 or 300 rows**, a baked-in **30% failure rate**, and an **~18% borderline band** (factuality 3↔4, task 3) with graded hallucination severity, format-only "halo" failures, and matched pass/fail pairs (same input, opposite verdict).
- **Three rubrics** — **Task Completion** (1–5, pass ≥3), **Format Adherence** (0/1), **Factuality** (1–5, pass ≥4); the verdict is *derived* from the scores, never hand-set. The **support** demo adds three domain rubrics — **Confidentiality / No-Leak**, **Escalation Correctness**, and **Tone**.
- **Three artifacts per demo:** a labeled gold side-file (full scores/verdict/failure-mode — never uploaded), a **TryEval Live** set (blank output; the platform calls the RAG endpoint), and a **TryEval Calibration** set (pre-filled output for cheap direct-eval, with the reference packed into `eval_context` so it reaches the judge but never the model — no leak).
- **A scorer** (`_score_<demo>_judge.py`) grades a judge export against gold: Cohen's κ, fail-class precision/recall, per-rubric threshold-crossing agreement, clear-vs-borderline stratification, matched-pair sensitivity, and (with two runs) borderline flip-rate. `--selftest` fabricates a noisy judge to prove the metrics end-to-end.

`<demo>-metrics.json` holds the TryEval rubric definitions (all grading anchors live in the option descriptions), and `<demo>-tryeval-setup.md` is the per-domain import/isolation/calibration-join guide.

See **[evals-strategy.md](evals-strategy.md)** for the full metric definitions, harness design, and CI integration.

---

## Deployment

The production target is a **Raspberry Pi 4 (4 GB)** behind a **Cloudflare Tunnel**:

- **ParadeDB** runs in Docker (`restart: unless-stopped`).
- **FastAPI** and **Next.js** run bare-metal under **systemd** (building torch + Next.js images on the Pi OOMs, so only the pre-built DB image is containerized).
- Ingest is a one-time job run on a dev machine; the resulting DB is dumped and restored on the Pi — **no GPU and no model download at query time** (all models are served via OpenRouter).

Full runbook (env, symlinks, dump/restore, systemd units, tunnel config, troubleshooting) is in **[DEPLOY.md](DEPLOY.md)**; rollback steps in **[ROLLBACK.md](ROLLBACK.md)**.

---

## Roadmap

The companion strategy docs propose concrete, measured upgrades:

- **Smarter chunking** per domain (structure-aware, parent-document/small-to-big, table handling) — see **[chunking-strategy.md](chunking-strategy.md)**.
- **Contextual embeddings** (Anthropic-style situating context + Contextual BM25, late chunking) to lift recall — see **[contextual-embeddings.md](contextual-embeddings.md)**.
- **A full evaluation harness** with recall@k / nDCG and an LLM judge wired into CI — see **[evals-strategy.md](evals-strategy.md)**.

---

## Companion docs

| Doc | What it covers |
|-----|----------------|
| [chunking-strategy.md](chunking-strategy.md) | Current chunking analysis + research-backed, per-domain recommendations |
| [contextual-embeddings.md](contextual-embeddings.md) | What contextual embeddings are and how to add them to this stack |
| [evals-strategy.md](evals-strategy.md) | Metrics, harness, regression oracle, and CI strategy |
| [insights-marketing.md](insights-marketing.md) | Résumé framing, social posts, and positioning (for the author) |

---

## License & disclaimers

This is a personal/portfolio project. The legal and health demos are **information tools, not professional advice** — every answer ends with the appropriate disclaimer, and the system is designed to refuse rather than guess.

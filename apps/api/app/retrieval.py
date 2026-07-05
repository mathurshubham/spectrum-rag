"""
Retrieval modes: vanilla, bm25, hybrid (RRF), hyde.

All modes tested in production.
vanilla  = dense kNN only
bm25     = BM25 full-text only
hybrid   = dense + BM25 → RRF fusion (default)
hyde     = generate hypothetical doc → embed → dense kNN

Every query is scoped to a single demo_id — zero cross-demo leakage.
"""
from __future__ import annotations

import asyncio

import psycopg
from psycopg.rows import dict_row

from .config import REPO_ROOT
from .db import get_pool
from .embed import embed_query

RRF_K = 60
DEFAULT_VISIBILITY: tuple[str, ...] = ("public",)

# ParadeDB / Tantivy Lucene-style special chars that must be escaped in BM25 queries
_BM25_SPECIALS = set(r'+-&|!(){}[]^"~*?:\/' + "'")


def _sanitize_bm25_query(q: str) -> str:
    """Strip Lucene-special chars from a BM25 query string.

    ParadeDB's @@@ parses queries with Lucene syntax; user-typed apostrophes,
    quotes, slashes, etc. blow up the parser. We strip rather than escape so
    French apostrophes like "l'éco-citoyenneté" turn into "l éco citoyenneté"
    and still match tokenized content.
    """
    return "".join(" " if c in _BM25_SPECIALS else c for c in q).strip() or "*"


def _load_hyde_prompt(demo_id: str) -> str:
    path = REPO_ROOT / "demos" / demo_id / "prompts" / "hyde.txt"
    if path.exists():
        return path.read_text()
    # Fallback — generic enough to work for any corpus
    return (
        "Write a short excerpt (2-4 sentences) that would directly answer "
        "the following question. Write only the content text, no preamble.\n\nQuestion: {query}"
    )


async def _dense(
    conn: psycopg.AsyncConnection, vec: list[float], top_k: int, demo_id: str,
    visibility: list[str], board: str | None = None, section_filter: str | None = None,
) -> list[dict]:
    where = ["demo_id = %s", "visibility = ANY(%s)"]
    params: list = [vec, demo_id, visibility]
    if board:
        where.append("metadata->>'board' = %s")
        params.append(board)
    if section_filter:
        where.append("section_ref ILIKE %s")
        params.append(f"%{section_filter}%")
    params += [vec, top_k]
    sql = f"""
        SELECT id, doc_id, doc_title, section_ref, content, visibility, metadata,
               1 - (embedding <=> %s::vector) AS score
        FROM chunks
        WHERE {' AND '.join(where)}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    cur = await conn.execute(sql, params)
    return await cur.fetchall()


async def _bm25(
    conn: psycopg.AsyncConnection, query: str, top_k: int, demo_id: str,
    visibility: list[str], board: str | None = None, section_filter: str | None = None,
) -> list[dict]:
    query = _sanitize_bm25_query(query)
    where = ["content @@@ %s", "demo_id = %s", "visibility = ANY(%s)"]
    params: list = [query, demo_id, visibility]
    if board:
        where.append("metadata->>'board' = %s")
        params.append(board)
    if section_filter:
        where.append("section_ref ILIKE %s")
        params.append(f"%{section_filter}%")
    params.append(top_k)
    sql = f"""
        SELECT id, doc_id, doc_title, section_ref, content, visibility, metadata,
               paradedb.score(id) AS score
        FROM chunks
        WHERE {' AND '.join(where)}
        ORDER BY score DESC
        LIMIT %s
    """
    cur = await conn.execute(sql, params)
    return await cur.fetchall()


def _rrf(dense_rows: list[dict], bm25_rows: list[dict], top_k: int) -> list[dict]:
    scores: dict[int, float] = {}
    by_id: dict[int, dict] = {}

    for rank, row in enumerate(dense_rows):
        rid = row["id"]
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (RRF_K + rank + 1)
        by_id[rid] = row

    for rank, row in enumerate(bm25_rows):
        rid = row["id"]
        scores[rid] = scores.get(rid, 0.0) + 1.0 / (RRF_K + rank + 1)
        by_id.setdefault(rid, row)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    result = []
    for rid, rrf_score in ranked:
        row = dict(by_id[rid])
        row["score"] = rrf_score
        result.append(row)
    return result


async def retrieve(
    query: str,
    demo_id: str,
    mode: str = "hybrid",
    top_k: int = 20,
    *,
    visibility: list[str] | None = None,
    openrouter_key: str | None = None,
    hyde_model: str | None = None,
    provider: str = "openrouter",
    openai_key: str | None = None,
    cf_account_id: str | None = None,
    cf_gateway_id: str | None = None,
    board: str | None = None,
    section_filter: str | None = None,
) -> list[dict]:
    vis = list(visibility) if visibility else list(DEFAULT_VISIBILITY)
    # Normalize board: "all" / "" / None → no filter
    if board and board.lower() in ("all", ""):
        board = None

    pool = await get_pool()
    async with pool.connection() as conn:
        conn.row_factory = dict_row

        if mode == "vanilla":
            vec = embed_query([query])[0]
            return await _dense(conn, vec, top_k, demo_id, vis, board, section_filter)

        if mode == "bm25":
            return await _bm25(conn, query, top_k, demo_id, vis, board, section_filter)

        if mode == "hybrid":
            vec = embed_query([query])[0]
            dense_rows, bm25_rows = await asyncio.gather(
                _dense(conn, vec, top_k, demo_id, vis, board, section_filter),
                _bm25(conn, query, top_k, demo_id, vis, board, section_filter),
            )
            return _rrf(dense_rows, bm25_rows, top_k)

        if mode == "hyde":
            from .gateway import chat_completion
            import os
            from .config import settings as _settings
            if provider == "openai":
                model = _settings.openai_fast_model
            else:
                model = hyde_model or os.getenv("HYDE_MODEL", "openai/gpt-4.1-mini")
            key = openrouter_key or ""
            hyde_prompt_tmpl = _load_hyde_prompt(demo_id)
            result = await chat_completion(
                messages=[{"role": "user", "content": hyde_prompt_tmpl.format(query=query)}],
                model=model,
                openrouter_key=key,
                provider=provider,
                openai_key=openai_key,
                account_id=cf_account_id,
                gateway_id=cf_gateway_id,
                max_tokens=256,
                temperature=0.3,
            )
            hypothetical_doc = result["text"].strip()
            vec = embed_query([hypothetical_doc])[0]
            return await _dense(conn, vec, top_k, demo_id, vis, board, section_filter)

        raise ValueError(f"Unknown retrieval mode: {mode!r}")

from contextlib import asynccontextmanager

import yaml
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import REPO_ROOT, settings
from .db import close_pool, get_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    # Warm local embedder only when OpenRouter API key not set
    if not settings.openrouter_api_key:
        from .embed import get_embedder
        get_embedder()
    yield
    await close_pool()


app = FastAPI(title="Spectrum RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")
    return {"status": "ok"}


@app.get("/api/demos")
async def list_demos():
    """Return all registered demos from the demos/ directory."""
    demos_root = REPO_ROOT / "demos"
    demos = []
    if demos_root.exists():
        for d in sorted(demos_root.iterdir()):
            manifest_path = d / "manifest.yaml"
            if d.is_dir() and manifest_path.exists():
                with open(manifest_path) as f:
                    m = yaml.safe_load(f)
                demos.append({
                    "id": m.get("demo_id", d.name),
                    "title": m.get("title", d.name),
                    "description": m.get("description", ""),
                })
    return {"demos": demos}


@app.get("/api/{demo}/corpus")
async def corpus_info(demo: str):
    """Return all ingested documents for a demo with chunk counts — live from DB."""
    from psycopg.rows import dict_row
    pool = await get_pool()
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        rows = await (await conn.execute(
            """
            SELECT doc_id, doc_title,
                   count(*) AS chunk_count,
                   count(DISTINCT section_ref) AS section_count
            FROM chunks
            WHERE demo_id = %s
            GROUP BY doc_id, doc_title
            ORDER BY doc_title
            """,
            (demo.lower(),),
        )).fetchall()
        total = await (await conn.execute(
            "SELECT count(*) AS n FROM chunks WHERE demo_id = %s",
            (demo.lower(),),
        )).fetchone()

    return {
        "demo_id": demo.lower(),
        "documents": [dict(r) for r in rows],
        "total_chunks": total["n"] if total else 0,
    }


from .dataset import dataset_info             # noqa: E402
from .query import router as query_router     # noqa: E402
app.add_api_route("/api/{demo}/dataset", dataset_info, methods=["GET"])
app.include_router(query_router)


# ── Teacher dashboard — chapter outline grouped by Leçon + chunk type ─────────
@app.get("/api/{demo}/chapters")
async def chapter_outline(demo: str, board: str | None = None):
    """Return chapter outline for browsing — used by teacher dashboard.

    Output:
      { "chapters": [
          { "id": "Leçon 6", "doc_id": "CBSE_10_ENTREJEUNES", "doc_title": "...",
            "board": "cbse", "level": "A2",
            "sections": [
              { "section_ref": "...", "type": "exercise", "skill": "mixed",
                "preview": "..."} ]
          },
          ... ]
      }
    """
    from psycopg.rows import dict_row
    pool = await get_pool()
    where = ["demo_id = %s"]
    params: list = [demo.lower()]
    if board and board not in ("all", ""):
        where.append("metadata->>'board' = %s")
        params.append(board)
    sql = f"""
        SELECT doc_id, doc_title,
               COALESCE(NULLIF(regexp_replace(section_ref, '.*§(Leçon \\d+).*', '\\1'), section_ref), 'Other') AS chapter,
               metadata->>'board'  AS board,
               metadata->>'level'  AS level,
               metadata->>'type'   AS type,
               metadata->>'skill'  AS skill,
               section_ref,
               LEFT(content, 120) AS preview
        FROM chunks
        WHERE {' AND '.join(where)}
        ORDER BY doc_id, chapter, section_ref
    """
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        rows = await (await conn.execute(sql, params)).fetchall()

    # Group by (doc_id, chapter)
    grouped: dict[tuple, dict] = {}
    for r in rows:
        key = (r["doc_id"], r["chapter"])
        if key not in grouped:
            grouped[key] = {
                "id": r["chapter"],
                "doc_id": r["doc_id"],
                "doc_title": r["doc_title"],
                "board": r["board"],
                "level": r["level"],
                "sections": [],
            }
        grouped[key]["sections"].append({
            "section_ref": r["section_ref"],
            "type": r["type"],
            "skill": r["skill"],
            "preview": r["preview"],
        })
    return {"demo_id": demo.lower(), "chapters": list(grouped.values())}


# ── Question generator (iter 8) ─────────────────────────────────────────────
from pydantic import BaseModel as _BM   # noqa: E402


class GenQuestionsReq(_BM):
    chapter: str | None = None       # e.g. "Leçon 6" / IB unit "8A" / null = whole corpus
    board: str | None = None         # cbse | ib | None=all
    grade: str | None = None         # CBSE "9" | "10" (else inferred from difficulty)
    count: int = 10
    difficulty: str | None = None    # A1 | A2 | B1 | B2 | null
    question_types: list[str] | None = None   # ["mcq","fill_in","short","essay","vrai_faux"]
    language_mode: str = "bilingual"
    mode: str = "practice_set"       # "exam_paper" | "practice_set"
    teacher_notes: str | None = None  # free-text teacher customization (highest priority)
    gen_model: str | None = None     # override generation model (else GEN_MODEL env)


@app.post("/api/{demo}/generate-questions")
async def generate_questions(
    demo: str,
    req: GenQuestionsReq,
    cf_account_id: str | None = None,
    cf_gateway_id: str | None = None,
    x_openrouter_key: Annotated[str | None, Header()] = None,
):
    """Build a question bank from indexed chunks. Powers teacher question-gen UI."""
    from .retrieval import retrieve as _retrieve
    from .gateway import chat_completion
    from .config import settings as _settings
    from .query import _boost_french_chunks, _detect_french_chapter, _detect_french_intent
    from . import question_gen as qg
    import os

    key = x_openrouter_key or _settings.openrouter_api_key
    if not key:
        raise HTTPException(status_code=401, detail="OpenRouter key required")

    count = max(1, min(req.count, 50))
    mode = req.mode if req.mode in ("exam_paper", "practice_set") else "practice_set"
    grade = qg.resolve_grade(req.board, req.grade, req.difficulty)
    chapter_filter = _detect_french_chapter(req.chapter or "") or req.chapter
    seed_query = " ".join(
        part for part in (
            req.chapter, req.difficulty,
            " ".join(req.question_types or []),
            "French exam question paper chapter overview vocabulary grammar comprehension",
        )
        if part
    )
    # exam papers need broad grade coverage; practice sets stay tighter
    top_k = 60 if mode == "exam_paper" else 40
    chunks = await _retrieve(
        seed_query, demo_id=demo.lower(),
        mode="hybrid", top_k=top_k,
        visibility=["public"],
        openrouter_key=key,
        cf_account_id=cf_account_id,
        cf_gateway_id=cf_gateway_id,
        board=req.board,
        section_filter=None,
    )
    chunks = _boost_french_chunks(
        chunks,
        chapter_filter=chapter_filter,
        intent=_detect_french_intent(seed_query + " teacher question bank"),
    )
    # hard grade/chapter scoping (fixes cross-chapter + cross-grade leak)
    chunks, scope_info = qg.scope_chunks(chunks, req.board, grade, chapter_filter)

    # chapter scope must not depend on semantic recall: fetch the chapter's chunks
    # directly by tag and use them as primary context when available.
    if chapter_filter:
        tag_chunks = await qg.fetch_chapter_chunks(demo.lower(), req.board, grade, chapter_filter)
        if tag_chunks:
            seen = {c["id"] for c in tag_chunks}
            filler = [c for c in chunks if c.get("id") not in seen]
            chunks = tag_chunks + filler
            scope_info["chapter_filtered"] = "db_tag"

    n_ctx = 20 if mode == "exam_paper" else 12

    def _format_chunk(c: dict) -> str:
        meta = c.get("metadata") or {}
        meta_bits = []
        if isinstance(meta, dict):
            for k in ("board", "level", "lecon", "lecon_title", "type", "skill", "header_path"):
                v = meta.get(k)
                if v:
                    meta_bits.append(f"{k}:{v}")
        meta_line = f"\n[metadata: {' | '.join(meta_bits)}]" if meta_bits else ""
        return f"[{c['section_ref']} — {c['doc_title']}]{meta_line}\n{c['content']}"

    context = "\n\n---\n\n".join(_format_chunk(c) for c in chunks[:n_ctx])

    model = req.gen_model or os.getenv("GEN_MODEL", "deepseek/deepseek-v3.2")
    # exam papers are long; generating the paper and its marking scheme in one call
    # truncates the key. Two-pass for exam_paper: questions, then a full key.
    if mode == "exam_paper":
        paper_prompt = qg.build_prompt(
            board=req.board, mode=mode, grade=grade, level=req.difficulty,
            chapter=req.chapter, count=count, question_types=req.question_types,
            language_mode=req.language_mode, teacher_notes=req.teacher_notes,
            context=context, include_key=False,
        )
        paper = await chat_completion(
            messages=[{"role": "user", "content": paper_prompt}], model=model,
            openrouter_key=key, account_id=cf_account_id, gateway_id=cf_gateway_id,
            max_tokens=5000, temperature=0.15,
        )
        key_prompt = qg.build_key_prompt(board=req.board, paper_md=paper["text"], context=context)
        key_res = await chat_completion(
            messages=[{"role": "user", "content": key_prompt}], model=model,
            openrouter_key=key, account_id=cf_account_id, gateway_id=cf_gateway_id,
            max_tokens=4000, temperature=0.2,
        )
        markdown = f"{paper['text']}\n\n{key_res['text']}"
    else:
        sys_prompt = qg.build_prompt(
            board=req.board, mode=mode, grade=grade, level=req.difficulty,
            chapter=req.chapter, count=count, question_types=req.question_types,
            language_mode=req.language_mode, teacher_notes=req.teacher_notes,
            context=context,
        )
        single = await chat_completion(
            messages=[{"role": "user", "content": sys_prompt}], model=model,
            openrouter_key=key, account_id=cf_account_id, gateway_id=cf_gateway_id,
            max_tokens=3000, temperature=0.15,
        )
        markdown = single["text"]
    return {
        "questions_markdown": markdown,
        "chunks_used": [
            {
                "section_ref": c["section_ref"],
                "doc_title": c["doc_title"],
                "metadata": c.get("metadata") or {},
                "retrieval_boost": c.get("retrieval_boost"),
                "boost_reasons": c.get("boost_reasons", []),
            }
            for c in chunks[:n_ctx]
        ],
        "config": {
            "chapter": req.chapter, "board": req.board, "grade": grade,
            "mode": mode, "count": count, "difficulty": req.difficulty,
            "question_types": req.question_types or ["mcq", "fill_in", "short"],
            "scope": scope_info,
        },
    }

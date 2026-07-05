from __future__ import annotations

import json
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .condense import condense_query
from .config import REPO_ROOT, settings
from .gateway import chat_completion, chat_completion_stream
from .rerank import rerank
from .retrieval import DEFAULT_VISIBILITY as _DEFAULT_VISIBILITY, retrieve

router = APIRouter()
_GEN_MODEL = settings.gen_model
_EMBED_MODEL = settings.embed_model

_FRENCH_TENSE_TERMS = (
    "passé composé", "passe compose", "imparfait", "plus-que-parfait",
    "plus que parfait", "futur", "conditionnel", "subjonctif", "présent",
    "present", "participe", "auxiliaire",
)
_FRENCH_GRAMMAR_MARKERS = (
    "grammar", "grammaire", "tense", "temps", "difference between",
    "différence entre", "conjug", "conjugaison", "explain", "explique",
)

# Bilingual topic map: query trigger terms (en + fr, lowercase) → French
# textbook content terms to look for in chunk text. Fixes recall misses where
# an English query term (e.g. "media") shares no token with the French chunk
# (e.g. "Les médias"). Applied as a soft additive boost, never a hard filter.
_FRENCH_TOPIC_TERMS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("media", "média", "médias", "press", "newspaper"),
     ("média", "médias", "presse", "télévision", "radio", "journal", "actualités")),
    (("shopping", "achats", "shop", "store", "buy"),
     ("achats", "magasin", "boulangerie", "épicerie", "supermarché", "marché")),
    (("family", "famille", "relatives", "parents"),
     ("famille", "père", "mère", "frère", "sœur", "soeur", "parents")),
    (("francophonie", "francophone", "french-speaking"),
     ("francophonie", "francophone", "sénégal", "québec", "pays")),
    (("food", "cooking", "cuisine", "nourriture", "meal"),
     ("cuisine", "repas", "recette", "manger", "plat", "nourriture")),
    (("health", "doctor", "médecin", "santé", "sick", "illness"),
     ("médecin", "malade", "patient", "ordonnance", "santé", "maladie")),
    (("environment", "environnement", "pollution", "ecology"),
     ("environnement", "pollution", "recyclage", "planète", "réchauffement", "écologie")),
    (("education", "school", "éducation", "studies"),
     ("éducation", "lycée", "collège", "bac", "école", "études")),
    (("travel", "voyage", "trip", "transport"),
     ("voyage", "transport", "train", "avion", "vacances")),
    (("work", "travail", "job", "career", "employment"),
     ("travail", "métier", "emploi", "profession", "carrière")),
    (("weather", "météo", "climate", "climat"),
     ("météo", "temps", "climat", "saison", "pluie")),
)


def _load_system_prompt(demo_id: str, version: str) -> str:
    path = REPO_ROOT / "demos" / demo_id / "prompts" / f"system_{version}.md"
    if not path.exists():
        raise ValueError(f"System prompt not found for demo={demo_id!r} version={version!r} at {path}")
    return path.read_text()


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        meta = c.get("metadata") or {}
        meta_bits = []
        if isinstance(meta, dict):
            for key in ("board", "level", "type", "skill", "header_path"):
                value = meta.get(key)
                if value:
                    meta_bits.append(f"{key}:{value}")
        meta_line = f"\n[metadata: {' | '.join(meta_bits)}]" if meta_bits else ""
        parts.append(
            f"[{c['section_ref']} — {c['doc_title']}]{meta_line}\n{c['content']}"
        )
    return "\n\n---\n\n".join(parts)


def _assemble_citations(chunks: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    citations = []
    for c in chunks:
        key = (c["doc_id"], c["section_ref"])
        if key not in seen:
            seen.add(key)
            citations.append({"section_ref": c["section_ref"], "doc_title": c["doc_title"]})
    return citations


def _detect_french_chapter(*texts: str) -> str | None:
    import re
    for q_text in texts:
        m = re.search(r"(?:le[çc]on|chapter|chapitre|lesson)\s+(\d+)", q_text, re.IGNORECASE)
        if m:
            return f"Leçon {m.group(1)}"
    return None


def _detect_french_intent(query: str) -> dict:
    q = query.lower()
    tense_hits = [t for t in _FRENCH_TENSE_TERMS if t in q]
    grammar_hit = any(m in q for m in _FRENCH_GRAMMAR_MARKERS)
    vocab_hit = any(m in q for m in ("vocab", "vocabulary", "lexique", "words for", "mots pour"))
    teacher_hit = any(m in q for m in ("lesson plan", "question bank", "exam", "worksheet", "teacher", "questions"))
    topic_terms: list[str] = []
    for triggers, content_terms in _FRENCH_TOPIC_TERMS:
        if any(t in q for t in triggers):
            topic_terms.extend(content_terms)
    return {
        "grammar": grammar_hit or len(tense_hits) >= 2,
        "vocab": vocab_hit,
        "teacher": teacher_hit,
        "tense_hits": tense_hits,
        "topic_terms": sorted(set(topic_terms)),
    }


def _chunk_type(chunk: dict) -> str:
    meta = chunk.get("metadata") or {}
    if isinstance(meta, dict):
        return str(meta.get("type") or "")
    return ""


def _boost_french_chunks(
    chunks: list[dict],
    *,
    chapter_filter: str | None,
    intent: dict,
) -> list[dict]:
    """Apply deterministic French retrieval preferences without dropping recall.

    This is intentionally a soft boost layer. Hard SQL chapter filters caused
    recall loss when OCR/heading parsing missed a Leçon tag.
    """
    if not chunks:
        return chunks

    topic_terms = [t.lower() for t in (intent.get("topic_terms") or [])]

    boosted = []
    for idx, chunk in enumerate(chunks):
        row = dict(chunk)
        ctype = _chunk_type(row)
        section_ref = row.get("section_ref", "")
        header_path = ""
        meta = row.get("metadata") or {}
        if isinstance(meta, dict):
            header_path = str(meta.get("header_path") or "")

        boost = 0.0
        reasons: list[str] = []
        if chapter_filter and (
            chapter_filter.lower() in section_ref.lower()
            or chapter_filter.lower() in header_path.lower()
        ):
            boost += 2.0
            reasons.append(f"chapter:{chapter_filter}")

        if topic_terms:
            haystack = f"{section_ref} {header_path} {row.get('content', '')}".lower()
            matched = {t for t in topic_terms if t in haystack}
            if matched:
                # Soft, capped: reward term overlap without overpowering chapter
                # or grammar-type signals. Section/header hits weigh double.
                term_boost = min(len(matched) * 0.4, 1.2)
                if any(t in f"{section_ref} {header_path}".lower() for t in matched):
                    term_boost = min(term_boost + 0.4, 1.5)
                boost += term_boost
                reasons.append(f"topic:{'+'.join(sorted(matched))}")

        if intent.get("grammar"):
            if ctype == "grammar":
                boost += 1.5
                reasons.append("intent:grammar")
            elif ctype == "revision":
                boost += 0.35
                reasons.append("intent:revision-ok")
            elif ctype == "exercise":
                boost -= 0.75
                reasons.append("intent:exercise-demote")
        elif intent.get("vocab"):
            if ctype == "vocab":
                boost += 1.2
                reasons.append("intent:vocab")
        elif intent.get("teacher"):
            if ctype in ("objectives", "exercise", "revision"):
                boost += 0.6
                reasons.append("intent:teacher")

        # Preserve existing rank as a small tie-breaker. Raw RRF/cosine/BM25
        # scores are not comparable to boosts, so keep this separate.
        row["retrieval_boost"] = round(boost, 3)
        row["boost_reasons"] = reasons
        row["_boost_rank_score"] = boost - (idx * 0.0001)
        boosted.append(row)

    return sorted(boosted, key=lambda c: c.get("_boost_rank_score", 0.0), reverse=True)


class Turn(BaseModel):
    role: str
    content: str


class QueryRequest(BaseModel):
    q: str
    history: list[Turn] = Field(default_factory=list)
    visibility: list[str] | None = None  # None → engine default (['public'])
    language_mode: str | None = None  # per-demo opt-in: "fr" | "en" | "bilingual"; ignored if prompt has no placeholder
    output_mode: str | None = None  # per-demo opt-in: "student" | "teacher" | "lesson_plan" | "question_bank"


class QueryResponse(BaseModel):
    answer: str
    retrieved_chunks: list[dict]
    citations: list[dict]
    config: dict
    usage: dict
    latency: dict
    trace_id: str


def _resolve_key(x_openrouter_key: str | None) -> str:
    key = x_openrouter_key or settings.openrouter_api_key or None
    if not key:
        raise HTTPException(status_code=401, detail="X-OpenRouter-Key header required")
    return key


def _resolve_openai_key(x_openai_key: str | None) -> str:
    key = x_openai_key or settings.openai_api_key or None
    if not key:
        raise HTTPException(status_code=401, detail="X-OpenAI-Key header required for provider=openai")
    return key


_OPENAI_DEFAULT_GEN = "gpt-4o"


def _serialize_chunks(chunks: list[dict]) -> list[dict]:
    return [
        {
            "id": c["id"],
            "doc_id": c["doc_id"],
            "doc_title": c["doc_title"],   # additive — server-authoritative label
            "section_ref": c["section_ref"],
            "content": c["content"][:400],
            "metadata": c.get("metadata") or {},
            "score": c.get("score", 0.0),
            "rerank_score": c.get("rerank_score"),
            "retrieval_boost": c.get("retrieval_boost"),
            "boost_reasons": c.get("boost_reasons", []),
        }
        for c in chunks
    ]


async def _prepare_generation(
    demo_id: str,
    req: QueryRequest,
    *,
    mode: str,
    top_k: int,
    top_n: int,
    do_rerank: bool,
    gen_model: str | None,
    reranker_model: str | None,
    prompt_version: str,
    cf_account_id: str | None,
    cf_gateway_id: str | None,
    board: str | None,
    openrouter_key: str,
    provider: str = "openrouter",
    openai_key: str | None = None,
    openai_model: str | None = None,
) -> dict:
    """Run condense → retrieve → rerank and build the generation messages.
    Returns everything both the streaming and non-streaming endpoints need so
    the pipeline stays in one place."""
    trace_id = str(uuid.uuid4())
    t_start = time.perf_counter()

    # condense
    t0 = time.perf_counter()
    history = [t.model_dump() for t in req.history]
    effective_q = await condense_query(
        req.q, history, openrouter_key,
        provider=provider, openai_key=openai_key,
        account_id=cf_account_id, gateway_id=cf_gateway_id,
    )
    condense_ms = int((time.perf_counter() - t0) * 1000)

    # retrieve
    t0 = time.perf_counter()
    chapter_filter: str | None = None
    french_intent: dict = {}
    if demo_id == "french":
        # Match against both the original query AND the condensed query
        # (condense may drop "chapter"). Use this as a soft boost after
        # retrieval, not a hard SQL filter, to avoid recall loss.
        chapter_filter = _detect_french_chapter(req.q, effective_q)
        french_intent = _detect_french_intent(f"{req.q}\n{effective_q}")

    chunks = await retrieve(
        effective_q,
        demo_id=demo_id,
        mode=mode,
        top_k=top_k,
        visibility=req.visibility,
        openrouter_key=openrouter_key,
        hyde_model=None,
        provider=provider,
        openai_key=openai_key,
        cf_account_id=cf_account_id,
        cf_gateway_id=cf_gateway_id,
        board=board,
        section_filter=None if demo_id == "french" else chapter_filter,
    )
    if demo_id == "french":
        chunks = _boost_french_chunks(
            chunks,
            chapter_filter=chapter_filter,
            intent=french_intent,
        )
    retrieve_ms = int((time.perf_counter() - t0) * 1000)

    # rerank → top_n
    t0 = time.perf_counter()
    rerank_ms = 0
    if do_rerank and chunks:
        rerank_top_n = top_n
        if demo_id == "french" and (
            french_intent.get("grammar") or french_intent.get("topic_terms")
        ):
            # Let the cross-encoder consider more candidates, then re-apply
            # deterministic type/topic boosts so revision/exercise chunks do
            # not crowd out grammar explanations, and so topic-term matches
            # the reranker down-ranked can still be recovered.
            rerank_top_n = min(len(chunks), max(top_n * 3, 15))
        chunks = await rerank(
            effective_q, chunks, rerank_top_n, openrouter_key,
            account_id=cf_account_id, gateway_id=cf_gateway_id,
            model=reranker_model,
        )
        if demo_id == "french":
            chunks = _boost_french_chunks(
                chunks,
                chapter_filter=chapter_filter,
                intent=french_intent,
            )[:top_n]
        rerank_ms = int((time.perf_counter() - t0) * 1000)
    else:
        chunks = chunks[:top_n]

    # build messages
    if provider == "openai":
        model = openai_model or _OPENAI_DEFAULT_GEN
    else:
        model = gen_model or _GEN_MODEL
    system_tmpl = _load_system_prompt(demo_id, prompt_version)
    context_str = _build_context(chunks)
    lang_mode = (req.language_mode or "bilingual").lower()
    if lang_mode not in ("fr", "en", "bilingual"):
        lang_mode = "bilingual"
    out_mode = (req.output_mode or "student").lower()
    if out_mode not in ("student", "teacher", "lesson_plan", "question_bank"):
        out_mode = "student"
    system_msg = (
        system_tmpl
        .replace("{context}", context_str)
        .replace("{language_mode}", lang_mode)
        .replace("{output_mode}", out_mode)
    )

    messages = [{"role": "system", "content": system_msg}]
    for turn in req.history[-10:]:
        messages.append({"role": turn.role, "content": turn.content})
    messages.append({"role": "user", "content": req.q})

    config = {
        "demo": demo_id,
        "mode": mode,
        "top_k": top_k,
        "top_n": top_n,
        "rerank": do_rerank,
        "provider": provider,
        "gen_model": model,
        "reranker_model": reranker_model or settings.reranker_model,
        "embed_model": _EMBED_MODEL,
        "prompt_version": prompt_version,
        "visibility": req.visibility or list(_DEFAULT_VISIBILITY),
        "chapter_filter": chapter_filter,
        "query_intent": french_intent if demo_id == "french" else {},
    }

    return {
        "trace_id": trace_id,
        "t_start": t_start,
        "messages": messages,
        "model": model,
        "chunks": chunks,
        "config": config,
        "latency": {
            "condense_ms": condense_ms,
            "retrieve_ms": retrieve_ms,
            "rerank_ms": rerank_ms,
        },
    }


@router.post("/api/{demo}/query", response_model=QueryResponse)
async def query(
    demo: str,
    req: QueryRequest,
    mode: str = "hybrid",
    top_k: int = 20,
    top_n: int = 5,
    do_rerank: bool = True,
    gen_model: str | None = None,
    reranker_model: str | None = None,
    prompt_version: str = "v1",
    cf_account_id: str | None = None,
    cf_gateway_id: str | None = None,
    board: str | None = None,
    provider: str = "openrouter",
    openai_model: str | None = None,
    x_openrouter_key: Annotated[str | None, Header()] = None,
    x_openai_key: Annotated[str | None, Header()] = None,
):
    x_openrouter_key = _resolve_key(x_openrouter_key)
    openai_key = _resolve_openai_key(x_openai_key) if provider == "openai" else None
    if provider == "openai":
        do_rerank = False  # OpenAI has no rerank endpoint; skip in OpenAI mode

    demo_id = demo.lower()
    if demo_id == "french":
        # French textbook retrieval needs a wider candidate set; the original
        # generic defaults were tuned for smaller/statutory corpora.
        if top_k == 20:
            top_k = 40
        if top_n == 5:
            top_n = 8

    prep = await _prepare_generation(
        demo_id, req,
        mode=mode, top_k=top_k, top_n=top_n, do_rerank=do_rerank,
        gen_model=gen_model, reranker_model=reranker_model,
        prompt_version=prompt_version,
        cf_account_id=cf_account_id, cf_gateway_id=cf_gateway_id,
        board=board, openrouter_key=x_openrouter_key,
        provider=provider, openai_key=openai_key, openai_model=openai_model,
    )

    t0 = time.perf_counter()
    gen_result = await chat_completion(
        messages=prep["messages"],
        model=prep["model"],
        openrouter_key=x_openrouter_key,
        provider=provider,
        openai_key=openai_key,
        account_id=cf_account_id,
        gateway_id=cf_gateway_id,
    )
    generate_ms = int((time.perf_counter() - t0) * 1000)
    total_ms = int((time.perf_counter() - prep["t_start"]) * 1000)

    return QueryResponse(
        answer=gen_result["text"],
        retrieved_chunks=_serialize_chunks(prep["chunks"]),
        citations=_assemble_citations(prep["chunks"]),
        config=prep["config"],
        usage=gen_result["usage"],
        latency={**prep["latency"], "generate_ms": generate_ms, "total_ms": total_ms},
        trace_id=prep["trace_id"],
    )


@router.post("/api/{demo}/query/stream")
async def query_stream(
    demo: str,
    req: QueryRequest,
    mode: str = "hybrid",
    top_k: int = 20,
    top_n: int = 5,
    do_rerank: bool = True,
    gen_model: str | None = None,
    reranker_model: str | None = None,
    prompt_version: str = "v1",
    cf_account_id: str | None = None,
    cf_gateway_id: str | None = None,
    board: str | None = None,
    provider: str = "openrouter",
    openai_model: str | None = None,
    x_openrouter_key: Annotated[str | None, Header()] = None,
    x_openai_key: Annotated[str | None, Header()] = None,
):
    x_openrouter_key = _resolve_key(x_openrouter_key)
    openai_key = _resolve_openai_key(x_openai_key) if provider == "openai" else None
    if provider == "openai":
        do_rerank = False  # OpenAI has no rerank endpoint; skip in OpenAI mode

    demo_id = demo.lower()
    if demo_id == "french":
        if top_k == 20:
            top_k = 40
        if top_n == 5:
            top_n = 8

    prep = await _prepare_generation(
        demo_id, req,
        mode=mode, top_k=top_k, top_n=top_n, do_rerank=do_rerank,
        gen_model=gen_model, reranker_model=reranker_model,
        prompt_version=prompt_version,
        cf_account_id=cf_account_id, cf_gateway_id=cf_gateway_id,
        board=board, openrouter_key=x_openrouter_key,
        provider=provider, openai_key=openai_key, openai_model=openai_model,
    )

    async def event_stream():
        # meta first — retrieval is done, so the client can render sources
        # immediately while generation streams in.
        meta = {
            "type": "meta",
            "retrieved_chunks": _serialize_chunks(prep["chunks"]),
            "citations": _assemble_citations(prep["chunks"]),
            "config": prep["config"],
            "trace_id": prep["trace_id"],
        }
        yield f"data: {json.dumps(meta)}\n\n"

        t0 = time.perf_counter()
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            async for event in chat_completion_stream(
                messages=prep["messages"],
                model=prep["model"],
                openrouter_key=x_openrouter_key,
                provider=provider,
                openai_key=openai_key,
                account_id=cf_account_id,
                gateway_id=cf_gateway_id,
            ):
                if event["type"] == "delta":
                    yield f"data: {json.dumps({'type': 'delta', 'text': event['text']})}\n\n"
                elif event["type"] == "done":
                    usage = event["usage"]
        except Exception as exc:  # noqa: BLE001 — surface to client, don't 500 mid-stream
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            return

        generate_ms = int((time.perf_counter() - t0) * 1000)
        total_ms = int((time.perf_counter() - prep["t_start"]) * 1000)
        done = {
            "type": "done",
            "usage": usage,
            "latency": {**prep["latency"], "generate_ms": generate_ms, "total_ms": total_ms},
        }
        yield f"data: {json.dumps(done)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

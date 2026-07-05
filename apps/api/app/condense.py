"""
Query condenser — single canonical prompt, not per-demo.
The condenser is domain-blind by design: it rewrites a follow-up using only
what is present in the prior turns, never injecting domain knowledge.
"""
from pathlib import Path

from .config import settings
from .gateway import chat_completion

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_CONDENSE_MODEL = settings.hyde_model  # fast/cheap model slot reused for condensing


def _load_condense_system() -> str:
    path = _PROMPTS_DIR / "condense.txt"
    if path.exists():
        return path.read_text().strip()
    # Inline fallback so the service starts even if file is missing
    return (
        "Rewrite the follow-up into a standalone question using only what is present "
        "in the prior turns. Resolve pronouns and implicit references into explicit terms. "
        "Do not add facts not present in the conversation. "
        "Output only the rewritten query — no explanation, no preamble."
    )


def _format_history(history: list[dict]) -> str:
    lines = []
    for turn in history[-6:]:  # last 3 exchanges max
        role = turn.get("role", "user")
        lines.append(f"{role.upper()}: {turn['content']}")
    return "\n".join(lines)


async def condense_query(
    query: str,
    history: list[dict],
    openrouter_key: str,
    *,
    provider: str = "openrouter",
    openai_key: str | None = None,
    account_id: str | None = None,
    gateway_id: str | None = None,
) -> str:
    if not history:
        return query

    system = _load_condense_system()
    context = _format_history(history)
    user_msg = f"Conversation so far:\n{context}\n\nFollow-up: {query}\n\nStandalone query:"

    model = settings.openai_fast_model if provider == "openai" else _CONDENSE_MODEL
    result = await chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        model=model,
        openrouter_key=openrouter_key,
        provider=provider,
        openai_key=openai_key,
        account_id=account_id,
        gateway_id=gateway_id,
        max_tokens=128,
        temperature=0.0,
    )
    # The cheap condense model occasionally returns null content; fall back to
    # the original query rather than 500 the whole request.
    condensed = (result.get("text") or "").strip().strip('"').strip("'")
    return condensed or query

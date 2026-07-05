import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_repo_root() -> Path:
    """Walk up from this file looking for the `demos/` directory.

    Works for both local dev (`apps/api/app/config.py` → repo root 4 levels up)
    and the docker image (`/app/app/config.py` where code lives at `/app/`).
    """
    env = os.environ.get("REPO_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / "demos").is_dir():
            return candidate
    # Fallback — preserves prior behaviour at original call site
    return here.parent.parent.parent.parent


REPO_ROOT: Path = _find_repo_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    openai_fast_model: str = "gpt-4o-mini"  # OpenAI-mode condense/HyDE model
    cf_account_id: str = ""
    cf_gateway_id: str = ""
    gen_model: str = "anthropic/claude-sonnet-4-5"
    embed_model: str = "baai/bge-m3"
    reranker_model: str = "nvidia/llama-nemotron-rerank-vl-1b-v2:free"
    hyde_model: str = "openai/gpt-4.1-mini"
    embed_batch_size: int = 64
    cors_origins: str = "http://localhost:3002"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

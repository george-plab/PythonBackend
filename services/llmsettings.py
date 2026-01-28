import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

try:
    from anthropic import Anthropic
except Exception:  # pragma: no cover - optional dependency
    Anthropic = None


class LLMSettings:
    def __init__(self, env_path: str | None = None) -> None:
        if env_path:
            load_dotenv(env_path, override=True)
        else:
            loaded = load_dotenv(override=True)
            if not loaded:
                project_root = Path(__file__).resolve().parents[1]
                fallback_env = project_root / ".env"
                if fallback_env.exists():
                    load_dotenv(fallback_env, override=True)

        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.lmstudio_base_url = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")

        self.model_chat_oa = os.getenv("MODEL_OA", "gpt-5-nano")
        self.model_chat_lm = os.getenv("MODEL_LM", "openai/gpt-oss-20b")
        self.model_classifier_oa = os.getenv("OMS_CLASSIFIER_MODEL", "gpt-5-nano")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

        self.openai_client: Optional[OpenAI] = None
        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)

        self.anthropic_client = None
        if self.anthropic_api_key and Anthropic is not None:
            self.anthropic_client = Anthropic(api_key=self.anthropic_api_key)

        self.lmstudio_client = OpenAI(
            base_url=self.lmstudio_base_url,
            api_key="lm-studio",
        )


_LLM_SETTINGS: Optional[LLMSettings] = None


def get_llmsettings() -> LLMSettings:
    global _LLM_SETTINGS
    if _LLM_SETTINGS is None:
        _LLM_SETTINGS = LLMSettings()
    return _LLM_SETTINGS

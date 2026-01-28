import os

import services.llmsettings as ls


class FakeOpenAI:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeAnthropic:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_llmsettings_creates_clients_when_keys_present(monkeypatch):
    monkeypatch.setattr(ls, "load_dotenv", lambda *args, **kwargs: True)
    monkeypatch.setenv("OPENAI_API_KEY", "oa-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "an-key")
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://lm")
    monkeypatch.setattr(ls, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(ls, "Anthropic", FakeAnthropic)

    llm = ls.LLMSettings()

    assert isinstance(llm.openai_client, FakeOpenAI)
    assert isinstance(llm.anthropic_client, FakeAnthropic)
    assert isinstance(llm.lmstudio_client, FakeOpenAI)
    assert llm.openai_client.kwargs["api_key"] == "oa-key"
    assert llm.anthropic_client.kwargs["api_key"] == "an-key"
    assert llm.lmstudio_client.kwargs["base_url"] == "http://lm"


def test_llmsettings_handles_missing_keys_gracefully(monkeypatch):
    monkeypatch.setattr(ls, "load_dotenv", lambda *args, **kwargs: True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://lm")
    monkeypatch.setattr(ls, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(ls, "Anthropic", FakeAnthropic)

    llm = ls.LLMSettings()

    assert llm.openai_client is None
    assert llm.anthropic_client is None
    assert isinstance(llm.lmstudio_client, FakeOpenAI)

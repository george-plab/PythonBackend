import pytest
from fastapi import HTTPException

from services import service_chatbot as sc


class FakeResponse:
    def __init__(self, output_text: str):
        self.output_text = output_text


class FakeResponses:
    def __init__(self, responses):
        self.calls = []
        self._responses = list(responses)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._responses:
            return self._responses.pop(0)
        return FakeResponse("ok")


class FakeClient:
    def __init__(self, responses):
        self.responses = responses


class FakeLLMSettings:
    def __init__(self, openai_client):
        self.openai_client = openai_client
        self.lmstudio_client = None
        self.model_chat_oa = "cloud-model"
        self.model_chat_lm = "local-model"


def test_build_instructions_uses_setting(monkeypatch):
    llm = FakeLLMSettings(openai_client=FakeClient(FakeResponses([FakeResponse("ok")])))
    llm.lmstudio_client = FakeClient(FakeResponses([FakeResponse("ok")]))
    chatbot = sc.ChatbotService(llm)
    setting = {"tone": "suave", "state": "triste", "mode": "night"}
    result = chatbot.build_instructions(setting)
    assert "suave" in result
    assert "triste" in result
    assert "night" in result


def test_chat_uses_local_client_when_use_local_true(monkeypatch):
    responses = FakeResponses([FakeResponse("ok")])
    local_client = FakeClient(responses)
    llm = FakeLLMSettings(openai_client=FakeClient(FakeResponses([FakeResponse("ok")])))
    llm.lmstudio_client = local_client
    chatbot = sc.ChatbotService(llm)

    response = chatbot.chat(
        message="hola",
        history=[],
        setting={},
        use_local=True,
    )

    assert responses.calls[0]["model"] == "local-model"
    assert responses.calls[0]["store"] is False
    assert response == "ok"


def test_chat_raises_when_no_openai_key_and_use_local_false(monkeypatch):
    llm = FakeLLMSettings(openai_client=None)
    llm.lmstudio_client = FakeClient(FakeResponses([FakeResponse("ok")]))
    chatbot = sc.ChatbotService(llm)

    with pytest.raises(HTTPException) as exc:
        chatbot.chat(message="hola", history=[], setting={}, use_local=False)

    assert exc.value.status_code == 500


def test_chat_injects_rag_context_into_instructions_when_present():
    responses = FakeResponses([FakeResponse("ok")])
    local_client = FakeClient(responses)
    llm = FakeLLMSettings(openai_client=FakeClient(FakeResponses([FakeResponse("ok")])))
    llm.lmstudio_client = local_client
    chatbot = sc.ChatbotService(llm)

    chatbot.chat(
        message="hola",
        history=[],
        setting={"_rag_context": "RAG_CONTEXT_START\nfoo\nRAG_CONTEXT_END"},
        use_local=True,
    )

    instructions = responses.calls[0]["instructions"]
    assert "Playbook guidance" in instructions
    assert "RAG_CONTEXT_START" in instructions

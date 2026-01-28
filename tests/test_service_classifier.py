from models.classifier import ClassifyResult
from services.service_classifier import ClassifierService
from services.llmsettings import LLMSettings


class FakeResponse:
    def __init__(self, output_text: str):
        self.output_text = output_text


class FakeResponses:
    def __init__(self, response):
        self._response = response

    def create(self, **_kwargs):
        return self._response


class FakeOpenAIClient:
    def __init__(self, response):
        self.responses = FakeResponses(response)


def test_classify_parses_json():
    llm = LLMSettings()
    llm.openai_client = FakeOpenAIClient(
        FakeResponse(
            '{"mood":"triste","intensity":3,"tone_hint":"suave",'
            '"night_mode_hint":false,"risk":"none","topics":["trabajo"]}'
        )
    )
    llm.model_classifier_oa = "classifier"
    service = ClassifierService(llm)

    result = service.classify("hola")

    assert result["mood"] == "triste"
    assert result["intensity"] == 3
    assert result["tone_hint"] == "suave"
    assert result["night_mode_hint"] is False
    assert result["risk"] == "none"
    assert result["topics"] == ["trabajo"]


def test_classify_returns_defaults_on_invalid_json():
    llm = LLMSettings()
    llm.openai_client = FakeOpenAIClient(FakeResponse("no-json"))
    llm.model_classifier_oa = "classifier"
    service = ClassifierService(llm)

    result = service.classify("hola")

    assert result == ClassifyResult.coerce_defaults({}).model_dump()

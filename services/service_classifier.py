import json

from models.classifier import ClassifyResult
from services.llmsettings import LLMSettings


class ClassifierService:
    def __init__(self, llm: LLMSettings) -> None:
        self.llm = llm
        self.client = llm.openai_client

    def _extract_json_object(self, text: str) -> dict:
        if not text:
            return {}
        text = text.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except Exception:
                return {}
        start = text.find("{")
        if start == -1:
            return {}
        depth = 0
        for idx in range(start, len(text)):
            ch = text[idx]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    snippet = text[start:idx + 1]
                    try:
                        return json.loads(snippet)
                    except Exception:
                        return {}
        return {}

    def _extract_response_text(self, response) -> str:
        text = getattr(response, "output_text", None)
        if text:
            return text
        try:
            return response.output[0].content[0].text
        except Exception:
            return ""

    def classify(self, message: str) -> dict:
        if self.client is None:
            return ClassifyResult.coerce_defaults({}).model_dump()

        instructions = (
            "Eres un clasificador emocional para OverMyShoulder. "
            "PROHIBIDO diagnosticar. Solo clasifica emocion, intensidad, riesgo y temas. "
            "Night mode si hay señales de insomnio o si el mensaje menciona noche/dormir. "
            "Si hay menciones claras de autolesion o deseo de morir -> risk='self_harm'. "
            "Si hay urgencia inminente, plan o intento -> risk='crisis'. "
            "Si no esta claro, usa risk='none'. "
            "Devuelve SOLO JSON valido, sin markdown ni texto extra. "
            "Estructura exacta (topics max 5):\n"
            "{"
            "\"mood\":\"triste|ansioso|solo|enfadado|confundido|neutro|alegre\","
            "\"intensity\":1-5,"
            "\"tone_hint\":\"suave|normal|directo\","
            "\"night_mode_hint\":true/false,"
            "\"risk\":\"none|self_harm|crisis\","
            "\"topics\":[\"ruptura\",\"insomnio\",\"pareja\",\"trabajo\",\"familia\",\"autoestima\",\"otro\"]"
            "}"
        )

        try:
            response = self.client.responses.create(
                model=self.llm.model_classifier_oa,
                reasoning={"effort": "low"},
                instructions=instructions,
                input=[{"role": "user", "content": message}],
                response_format={"type": "json_object"},
                max_output_tokens=160,
                store=False,
            )
            raw = self._extract_response_text(response)
            parsed = self._extract_json_object(raw)
            return ClassifyResult.coerce_defaults(parsed).model_dump()
        except Exception:
            return ClassifyResult.coerce_defaults({}).model_dump()

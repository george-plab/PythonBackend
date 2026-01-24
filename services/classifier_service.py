import json
import os
from typing import List, Dict, Any, Optional

from openai import OpenAI

from models.classifier import ClassifyResult


_CLIENT_OA = OpenAI()
_CLIENT_LM = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

_MODEL_CLASSIFIER_OA = os.getenv("OMS_CLASSIFIER_MODEL", "gpt-4o-mini")
_MODEL_CLASSIFIER_LM = os.getenv("OMS_CLASSIFIER_MODEL_LOCAL", "openai/gpt-oss-20b")


def _extract_response_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    try:
        return response.output[0].content[0].text
    except Exception:
        return ""


def _safe_history(history: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not isinstance(history, list):
        return []
    trimmed = history[-3:]
    return [item for item in trimmed if isinstance(item, dict)]


def classify_oms(message: str, history: List[Dict], setting: Dict, use_local: bool) -> dict:
    """
    Clasifica el estado emocional. Devuelve JSON estricto como dict.
    """
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

    input_messages = _safe_history(history) + [{"role": "user", "content": message}]
    client = _CLIENT_LM if use_local else _CLIENT_OA
    model = _MODEL_CLASSIFIER_LM if use_local else _MODEL_CLASSIFIER_OA

    try:
        response = client.responses.create(
            model=model,
            reasoning={"effort": "low"},
            instructions=instructions,
            input=input_messages,
            response_format={"type": "json_object"},
            max_output_tokens=120,
            store=False
        )
        raw = _extract_response_text(response)
        parsed = json.loads(raw)
        return ClassifyResult.coerce_defaults(parsed).model_dump()
    except Exception:
        return ClassifyResult.coerce_defaults({}).model_dump()

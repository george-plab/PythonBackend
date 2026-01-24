from enum import Enum
from typing import List, Any, Dict

from pydantic import BaseModel, field_validator


class Mood(str, Enum):
    triste = "triste"
    ansioso = "ansioso"
    solo = "solo"
    enfadado = "enfadado"
    confundido = "confundido"
    neutro = "neutro"
    alegre = "alegre"


class ToneHint(str, Enum):
    suave = "suave"
    normal = "normal"
    directo = "directo"


class Risk(str, Enum):
    none = "none"
    self_harm = "self_harm"
    crisis = "crisis"


class ClassifyResult(BaseModel):
    mood: Mood
    intensity: int
    tone_hint: ToneHint
    night_mode_hint: bool
    risk: Risk
    topics: List[str]

    @field_validator("intensity")
    def validate_intensity(cls, value: int) -> int:
        if not isinstance(value, int) or not (1 <= value <= 5):
            raise ValueError("intensity must be 1..5")
        return value

    @field_validator("topics")
    def validate_topics(cls, value: List[str]) -> List[str]:
        if not isinstance(value, list):
            raise ValueError("topics must be a list")
        allowed = {"ruptura", "insomnio", "pareja", "trabajo", "familia", "autoestima", "otro"}
        unique = []
        for item in value:
            if item in allowed and item not in unique:
                unique.append(item)
        if not unique:
            raise ValueError("topics must include at least one allowed value")
        return unique[:5]

    @classmethod
    def coerce_defaults(cls, payload: Dict[str, Any]) -> "ClassifyResult":
        defaults = {
            "mood": "neutro",
            "intensity": 2,
            "tone_hint": "suave",
            "night_mode_hint": False,
            "risk": "none",
            "topics": ["otro"],
        }
        try:
            if isinstance(payload, dict):
                merged = {**defaults, **payload}
            else:
                merged = defaults
            return cls.model_validate(merged)
        except Exception:
            return cls.model_validate(defaults)

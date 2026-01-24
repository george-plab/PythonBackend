import unittest

from models.classifier import ClassifyResult


class TestValidateClassification(unittest.TestCase):
    def test_defaults_on_invalid_input(self):
        result = ClassifyResult.coerce_defaults("nope").model_dump()
        self.assertEqual(result["mood"], "neutro")
        self.assertEqual(result["intensity"], 2)
        self.assertEqual(result["tone_hint"], "suave")
        self.assertEqual(result["night_mode_hint"], False)
        self.assertEqual(result["risk"], "none")
        self.assertEqual(result["topics"], ["otro"])

    def test_invalid_values_fall_back(self):
        payload = {
            "mood": "furioso",
            "intensity": 9,
            "tone_hint": "fuerte",
            "night_mode_hint": "si",
            "risk": "maybe",
            "topics": ["pareja", "invalid", "pareja"]
        }
        result = ClassifyResult.coerce_defaults(payload).model_dump()
        self.assertEqual(result["mood"], "neutro")
        self.assertEqual(result["intensity"], 2)
        self.assertEqual(result["tone_hint"], "suave")
        self.assertEqual(result["night_mode_hint"], False)
        self.assertEqual(result["risk"], "none")
        self.assertEqual(result["topics"], ["otro"])

    def test_accepts_valid_payload(self):
        payload = {
            "mood": "triste",
            "intensity": 3,
            "tone_hint": "normal",
            "night_mode_hint": True,
            "risk": "self_harm",
            "topics": ["familia", "autoestima"]
        }
        result = ClassifyResult.coerce_defaults(payload).model_dump()
        self.assertEqual(result, payload)

    def test_partial_payload_merges_defaults(self):
        payload = {
            "mood": "alegre",
            "intensity": 4,
            "tone_hint": "directo",
            "night_mode_hint": True
        }
        result = ClassifyResult.coerce_defaults(payload).model_dump()
        self.assertEqual(result["mood"], "alegre")
        self.assertEqual(result["intensity"], 4)
        self.assertEqual(result["tone_hint"], "directo")
        self.assertEqual(result["night_mode_hint"], True)
        self.assertEqual(result["risk"], "none")
        self.assertEqual(result["topics"], ["otro"])

    def test_topics_trim_to_five(self):
        payload = {
            "mood": "neutro",
            "intensity": 2,
            "tone_hint": "suave",
            "night_mode_hint": False,
            "risk": "none",
            "topics": ["ruptura", "insomnio", "pareja", "trabajo", "familia", "autoestima"]
        }
        result = ClassifyResult.coerce_defaults(payload).model_dump()
        self.assertEqual(len(result["topics"]), 5)


if __name__ == "__main__":
    unittest.main()

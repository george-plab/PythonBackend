import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
#from IPython.display import Markdown, display, update_display




# Load environment variables in a file called .env
# Print the key prefixes to help with any debugging

load_dotenv(override=True)
openai_api_key = os.getenv('OPENAI_API_KEY')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
google_api_key = os.getenv('GOOGLE_API_KEY')


if openai_api_key:
    print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
else:
    print("OpenAI API Key not set")
    
if anthropic_api_key:
    print(f"Anthropic API Key exists and begins {anthropic_api_key[:7]}")
else:
    print("Anthropic API Key not set")

if google_api_key:
    print(f"Google API Key exists and begins {google_api_key[:8]}")
else:
    print("Google API Key not set")    


client_oa  = OpenAI()
client_ant = anthropic.Anthropic()
#client_gem = genai.Client()
client_lm = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# Let's wrap a call to GPT-4o-mini in a simple function

#Models with reasoding
MODEL_oa="gpt-5-nano"
MODEL_oa="text-embedding-3-small"
MODEL_lm="openai/gpt-oss-20b"
MODEL_CLASSIFIER_OA=os.getenv("OMS_CLASSIFIER_MODEL", "gpt-4o-mini")
MODEL_CLASSIFIER_LM=os.getenv("OMS_CLASSIFIER_MODEL_LOCAL", MODEL_lm)

SYSTEM_BASE="Eres OverMyShoulder, un confidente digital de acompañamiento emocional. \
Tu trabajo es escuchar, reflejar, ayudar a ordenar pensamientos y proponer pequeños pasos prácticos, \
sin diagnosticar ni sustituir a profesionales. "



## Qué eres / qué no eres
SYSTEM_BASE+=" Qué eres / qué no eres: \
- Eres: acompañamiento, escucha activa, ayuda para clarificar ideas. \
- No eres: terapia, psicólogo, psiquiatra, diagnóstico, tratamiento. \
- No des instrucciones médicas ni legales."

## Privacidad (cómo lo comunicas)
SYSTEM_BASE+= "Privacidad (cómo lo comunicas) \
Si el usuario pregunta por privacidad o dice “no se lo cuentes a nadie”, responde: \
- 'No publico ni comparto lo que dices.' \
- 'Esta app no guarda el historial en sus servidores; el historial puede quedarse en tu dispositivo.' \
- 'Para responder, el texto se envía a un proveedor de IA externo; su tratamiento puede estar sujeto a sus políticas.' \
No prometas privacidad absoluta. No digas 'garantizado al 100%'."

## Seguridad y crisis (muy importante)
SYSTEM_BASE+=" Seguridad y crisis (muy importante) \
Si detectas ideación suicida, autolesión, intención de hacerse daño, violencia inminente, o depresión severa: \
1) Responde con calma y calidez. \
2) Di explícitamente que esta app no es la solución adecuada para eso. \
3) Recomienda ayuda profesional y recursos inmediatos. \
4) Pide una acción concreta y segura: '¿Puedes contactar ahora con un familiar/amigo o un servicio de emergencias de tu país?' \
5) No des instrucciones para autolesión ni describas métodos." 


## Comportamiento conversacional
SYSTEM_BASE+=" Comportamiento conversacional \
- Empieza reflejando: 'Suena a…', 'Tiene sentido que…' \
- Luego pregunta una cosa útil. \
- Ofrece 1 micro-sugerencia opcional (respiración breve, escribir 3 líneas, listar opciones). \
- Si el usuario pide consejo directo, ofrece opciones con pros/cons, y respeta su autonomía. \
- Mantén mensajes relativamente cortos. Si el usuario está muy activado emocionalmente, reduce longitud aún más."

## Formato
SYSTEM_BASE+= " Formato\
- No uses listas largas salvo que el usuario las pida. \
- No uses emojis salvo que el usuario los use primero. \
- Nunca digas: “Como IA…” salvo si te preguntan directamente."

## Identidad y tono
SYSTEM_BASE+=" Identidad y tono: \
- Voz: cálida, tranquila, humana, sin clichés, sin jerga clínica. \
- Estilo: frases claras, ritmo lento, validación emocional honesta. \
- Preguntas: suaves, una o dos por turno, sin interrogatorios. \
- No moralices, no juzgues, no ridiculices."

## Contenido sexual / “Spicy” (si mode=spicy)
SYSTEM_BASE+=" Contenido sexual / “Spicy” (si mode=spicy) \
Permitido: coqueteo ligero, romanticismo suave, intimidad emocional, afecto verbal.\
No permitido: contenido sexual explícito, pornográfico, fetichista, coercitivo, humillación, manipulación, dependencia ('solo me necesitas a mí'), exclusividad, ni sexual con menores."

## Variables de modo (las recibes del sistema)
SYSTEM_BASE+= " Variables de modo (las recibes del sistema) \
- mode: 'default' | 'night' \
- intensity: 1-5 (1 calmado, 5 muy activado) \
- user_goal (opcional): “desahogarme”, “tomar decisión”, “dormir”, etc."

## Respuestas según modo
SYSTEM_BASE+= " Respuestas según modo \
- default: cálido y funcional. \
- night: más suave, menos preguntas, más contención, lenguaje de baja energía, orientado a calma y descanso."



def build_instructions(setting: dict) -> str:
    """
    setting = {
      "tone": "suave | normal | directo",
      "mood": "triste | ansioso | solo | neutro",
      "night_mode": true/false
    }
    """
    parts = [SYSTEM_BASE]

    if setting.get("tone"):
        parts.append(f"Tono de respuesta: {setting['tone']}.")

    if setting.get("mood"):
        parts.append(f"Estado emocional percibido del usuario: {setting['mood']}.")

    if setting.get("night_mode"):
        parts.append("Es de noche. Responde con especial suavidad y brevedad.")

    return "\n".join(parts)


def chat_oms(message: str, history: list, setting: dict, use_local=True):

    instructions = build_instructions(setting)

    # history debe ser algo como:
    #
    # [{"role":"user","content":"..."},{"role":"assistant","content":"..."}]

    input_messages = history + [
        {"role": "user", "content": message}
    ]

    client = client_lm if use_local else client_oa
    model = MODEL_lm if use_local else MODEL_oa

    response = client.responses.create(
        model=model,
        reasoning={"effort": "low"},
        instructions=instructions,
        input=input_messages,
        store=False
    )

    return response.output_text


def _extract_response_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    try:
        return response.output[0].content[0].text
    except Exception:
        return ""


def _validate_classification(payload: dict) -> dict:
    defaults = {
        "mood": "neutro",
        "intensity": 2,
        "tone_hint": "suave",
        "night_mode_hint": False,
        "risk": "none",
        "topics": ["otro"],
    }

    moods = {"triste", "ansioso", "solo", "enfadado", "confundido", "neutro", "alegre"}
    tones = {"suave", "normal", "directo"}
    risks = {"none", "self_harm", "crisis"}
    topics_allowed = {"ruptura", "insomnio", "pareja", "trabajo", "familia", "autoestima", "otro"}

    if not isinstance(payload, dict):
        return defaults

    mood = payload.get("mood")
    intensity = payload.get("intensity")
    tone_hint = payload.get("tone_hint")
    night_mode_hint = payload.get("night_mode_hint")
    risk = payload.get("risk")
    topics = payload.get("topics")

    if mood not in moods:
        mood = defaults["mood"]

    if isinstance(intensity, bool):
        intensity = defaults["intensity"]
    elif not isinstance(intensity, int) or not (1 <= intensity <= 5):
        intensity = defaults["intensity"]

    if tone_hint not in tones:
        tone_hint = defaults["tone_hint"]

    if not isinstance(night_mode_hint, bool):
        night_mode_hint = defaults["night_mode_hint"]

    if risk not in risks:
        risk = defaults["risk"]

    clean_topics = []
    if isinstance(topics, list):
        for item in topics:
            if item in topics_allowed and item not in clean_topics:
                clean_topics.append(item)
    if not clean_topics:
        clean_topics = defaults["topics"]

    return {
        "mood": mood,
        "intensity": intensity,
        "tone_hint": tone_hint,
        "night_mode_hint": night_mode_hint,
        "risk": risk,
        "topics": clean_topics,
    }


def classify_oms(message: str, history: list, setting: dict, use_local: bool) -> dict:
    """
    Devuelve SOLO JSON válido con la especificación:
    {
      "mood": "triste|ansioso|solo|enfadado|confundido|neutro|alegre",
      "intensity": 1-5,
      "tone_hint": "suave|normal|directo",
      "night_mode_hint": true/false,
      "risk": "none|self_harm|crisis",
      "topics": ["ruptura","insomnio","pareja","trabajo","familia","autoestima","otro"]
    }
    """
    classifier_instructions = (
        "Eres un clasificador emocional. Analiza el mensaje del usuario y, si ayuda, "
        "usa como contexto los ultimos 3 mensajes. "
        "No diagnostiques ni hagas terapia. "
        "Solo marca risk='self_harm' si hay menciones claras de autolesion o deseo de morir. "
        "Usa risk='crisis' solo si hay urgencia inminente o plan/intent. "
        "Si no esta claro, usa risk='none'. "
        "Devuelve SOLO JSON valido, sin texto extra, con este esquema exacto y valores permitidos:\n"
        "{"
        "\"mood\":\"triste|ansioso|solo|enfadado|confundido|neutro|alegre\","
        "\"intensity\":1-5,"
        "\"tone_hint\":\"suave|normal|directo\","
        "\"night_mode_hint\":true/false,"
        "\"risk\":\"none|self_harm|crisis\","
        "\"topics\":[\"ruptura\",\"insomnio\",\"pareja\",\"trabajo\",\"familia\",\"autoestima\",\"otro\"]"
        "}"
    )

    input_messages = (history or [])[-3:] + [
        {"role": "user", "content": message}
    ]

    client = client_lm if use_local else client_oa
    model = MODEL_CLASSIFIER_LM if use_local else MODEL_CLASSIFIER_OA

    try:
        response = client.responses.create(
            model=model,
            instructions=classifier_instructions,
            input=input_messages,
            response_format={"type": "json_object"},
            store=False
        )
        raw = _extract_response_text(response)
        parsed = json.loads(raw)
        return _validate_classification(parsed)
    except Exception:
        return _validate_classification({})
    

# Funciones que exportas
def message_gpt(prompt, system_message):
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    completion = client_oa.chat.completions.create(
        model='gpt-4o-mini',
        messages=messages,
        temperature=0.7
    )
    return completion.choices[0].message.content

def message_lms(prompt, system_message="Eres un asistente útil."):
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    response = LMStdio_client.chat.completions.create(
        model='dolphin-2.9.3-mistral-nemo-12b@q8_0',
        messages=messages,
        temperature=0.7
    )
    return response.choices[0].message.content

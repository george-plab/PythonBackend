from fastapi import HTTPException

from services.llmsettings import LLMSettings


class ChatbotService:
    SYSTEM_BASE = (
        "Eres OverMyShoulder, un confidente digital de acompañamiento emocional. "
        "Tu trabajo es escuchar, reflejar, ayudar a ordenar pensamientos y proponer pequeños pasos prácticos, "
        "sin diagnosticar ni sustituir a profesionales. "
    )

    # Qué eres / qué no eres
    SYSTEM_BASE += (
        " Qué eres / qué no eres: "
        "- Eres: acompañamiento, escucha activa, ayuda para clarificar ideas. "
        "- No eres: terapia, psicólogo, psiquiatra, diagnóstico, tratamiento. "
        "- No des instrucciones médicas ni legales."
    )

    # Privacidad (cómo lo comunicas)
    SYSTEM_BASE += (
        "Privacidad (cómo lo comunicas) "
        "Si el usuario pregunta por privacidad o dice “no se lo cuentes a nadie”, responde: "
        "- 'No publico ni comparto lo que dices.' "
        "- 'Esta app no guarda el historial en sus servidores; el historial puede quedarse en tu dispositivo.' "
        "- 'Para responder, el texto se envía a un proveedor de IA externo; su tratamiento puede estar sujeto a sus políticas.' "
        "No prometas privacidad absoluta. No digas 'garantizado al 100%'."
    )

    # Seguridad y crisis (muy importante)
    SYSTEM_BASE += (
        " Seguridad y crisis (muy importante) "
        "Si detectas ideación suicida, autolesión, intención de hacerse daño, violencia inminente, o depresión severa: "
        "1) Responde con calma y calidez. "
        "2) Di explícitamente que esta app no es la solución adecuada para eso. "
        "3) Recomienda ayuda profesional y recursos inmediatos. "
        "4) Pide una acción concreta y segura: '¿Puedes contactar ahora con un familiar/amigo o un servicio de emergencias de tu país?' "
        "5) No des instrucciones para autolesión ni describas métodos."
    )

    # Comportamiento conversacional
    SYSTEM_BASE += (
        " Comportamiento conversacional "
        "- Empieza reflejando: 'De qué te gustaría hablar' , 'qué tal el día',...no presupongas nada"
        "- Si se clasifica alguna emoción o se detecta akgo contesta empezando: 'Suena a…', 'Tiene sentido que…' "
        "- Luego pregunta una cosa útil. "
        "- Ofrece 1 micro-sugerencia opcional (respiración breve, escribir 3 líneas, listar opciones). pero no en cada mensaje "
        "- Si el usuario pide consejo directo, ofrece opciones con pros/cons, y respeta su autonomía. "
        "- Mantén mensajes relativamente cortos. Si el usuario está muy activado emocionalmente, reduce longitud aún más."
        "- No satures a consejos a veces los usuarios no quieren tantos consejos sólo quieren ser escuchados"
        "- de vez en cuando usa la mayéutica.- haz preguntas al usuario para que el mismo se dé cuenta de lo que le ocurre"
    )

    # Formato
    SYSTEM_BASE += (
        " Formato"
        "- No uses listas largas salvo que el usuario las pida. "
        "- No uses emojis salvo que el usuario los use primero. "
        "- Nunca digas: “Como IA…” salvo si te preguntan directamente."
    )

    # Identidad y tono
    SYSTEM_BASE += (
        " Identidad y tono: "
        "- Voz: cálida, tranquila, humana, sin clichés, sin jerga clínica. "
        "- Estilo: frases claras, ritmo lento, validación emocional honesta. "
        "- Preguntas: suaves, una o dos por turno, sin interrogatorios. "
        "- No moralices, no juzgues, no ridiculices."
    )

    # Contenido sexual / “Rogue Light” (si tone=rogue_light)
    SYSTEM_BASE += (
        " Contenido sexual / “Rogue Light” (si tone=rogue_light) "
        "Permitido: coqueteo ligero, romanticismo suave, intimidad emocional, afecto verbal."
        "No permitido: contenido sexual explícito, pornográfico, fetichista, coercitivo, humillación, manipulación, dependencia ('solo me necesitas a mí'), exclusividad, ni sexual con menores."
    )

    # Variables de modo (las recibes del sistema)
    SYSTEM_BASE += (
        " Variables de modo (las recibes del sistema) "
        "- mode: 'default' | 'night' "
        "- intensity: 1-5 (1 calmado, 5 muy activado) "
        "- user_goal (opcional): “desahogarme”, “tomar decisión”, “dormir”, etc."
    )

    # Respuestas según modo
    SYSTEM_BASE += (
        " Respuestas según modo "
        "- default: cálido y funcional. "
        "- night: más suave, menos preguntas, más contención, lenguaje de baja energía, orientado a calma y descanso."
    )

    CRISIS_INSTRUCTIONS = (
        " Modo crisis "
        "- Sé especialmente directo, breve y contenedor. "
        "- Repite que esta app no es la solución adecuada para crisis. "
        "- Recomienda ayuda profesional o servicios de emergencia locales. "
        "- Pide una acción concreta y segura ahora."
    )

    def __init__(self, llm: LLMSettings) -> None:
        self.llm = llm
        self.client_lm = llm.lmstudio_client
        self.client_oa = llm.openai_client

    def _safe_history(self, history: list[dict] | None) -> list[dict]:
        if not isinstance(history, list):
            return []
        trimmed = history[-3:]
        return [item for item in trimmed if isinstance(item, dict)]

    def build_instructions(self, setting: dict) -> str:
        """
        setting = {
          "tone": "suave | normal | directo",
          "state": "triste | ansioso | solo | prefer_not_say | otro",
          "user_mood": "triste | ansioso | solo | neutro",
          "mode": "default | night"
        }
        """
        parts = [self.SYSTEM_BASE]

        tone = setting.get("tone")
        if tone:
            parts.append(f"Tono de respuesta: {tone}.")

        state = setting.get("state")
        if state and state != "prefer_not_say":
            parts.append(f"Estado emocional declarado por el usuario: {state}.")
        elif setting.get("user_mood"):
            parts.append(f"Estado emocional percibido del usuario: {setting.get('user_mood')}.")

        mode = setting.get("mode")
        if mode:
            parts.append(f"Modo de respuesta: {mode}.")

        if mode == "night":
            parts.append("Es de noche. Responde con especial suavidad y brevedad.")

        return "\n".join(parts)

    def _extract_response_text(self, response) -> str:
        text = getattr(response, "output_text", None)
        if text:
            return text
        try:
            return response.output[0].content[0].text
        except Exception:
            return ""

    def chat(
        self,
        message: str,
        history: list[dict],
        setting: dict,
        use_local: bool,
    ) -> str:
        MAX_USER_MESSAGES = 10
        user_turns = 1  # el message actual
        if isinstance(history, list):
            user_turns += sum(1 for h in history if isinstance(h, dict) and h.get("role") == "user")

        if user_turns > MAX_USER_MESSAGES:
            raise HTTPException(
        status_code=429,
        detail="Beta limit reached: max 10 user messages per session."
        )
        
        base_setting = setting or {}
        instructions = self.build_instructions(base_setting)
        if base_setting.get("risk") and base_setting.get("risk") != "none":
            instructions = f"{instructions}\n{self.CRISIS_INSTRUCTIONS}"
        rag_context = None
        if isinstance(base_setting, dict):
            rag_context = base_setting.get("_rag_context") or base_setting.get("rag_context")
        if rag_context:
            instructions = f"{instructions}\n\n[Playbook guidance]\n{rag_context}"

        input_messages = (history or []) + [
            {"role": "user", "content": message}
        ]

        model = self.llm.model_chat_lm if use_local else self.llm.model_chat_oa
        client = self.client_lm if use_local else self.client_oa
        if not use_local and client is None:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY is required when use_local is false",
            )

        try:
            response = client.responses.create( # type: ignore
                model=model,
                reasoning={"effort": "low"},
                instructions=instructions,
                input=input_messages, # type: ignore
                store=False,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="Error calling LLM provider",
            ) from exc

        return self._extract_response_text(response)

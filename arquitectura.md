  
Esta arquitectura sigue un principio claro:

Un solo punto de verdad para modelos y claves.
Servicios especializados, sin duplicación de clientes.
main.py como orquestador, no como cerebro.

🧩 Componentes Principales
1️⃣ LLMSettings

📍 Único sitio donde se definen claves, modelos y clientes

Responsabilidad

Cargar variables de entorno (.env)

Definir modelos activos (chat, clasificación, embeddings)

Crear y mantener una única instancia de cada cliente LLM

Gestiona

OPENAI_API_KEY

ANTHROPIC_API_KEY

LMSTUDIO_BASE_URL

Clientes creados

llm.openai_client → OpenAI (cloud)

llm.anthropic_client → Claude (preparado, opcional)

llm.lmstudio_client → LM Studio (local)

Modelos definidos

Chat (cloud): gpt-5-nano

Chat (local): openai/gpt-oss-20b

Clasificación emocional: gpt-5-nano

Embeddings (FAISS): text-embedding-3-small

🔒 Ningún otro archivo crea clientes ni lee claves directamente.


2️⃣ ClassifierService

📍 Clasificación emocional y de riesgo (cloud-only)

Responsabilidad

Analizar el mensaje actual del usuario

Devolver un JSON estructurado con:

mood

intensity

tone_hint

risk

topics

Características

Usa exclusivamente llm.openai_client

No usa historial (solo el mensaje actual)

Respuestas cortas y baratas (≈120 tokens)

Parseo robusto (tolerante a ruido)

Motivación

La clasificación debe ser estable y fiable

Los modelos locales no garantizan JSON estricto

3️⃣ RagFaissService

📍 Recuperación de contexto (RAG) con FAISS

Responsabilidad

Cargar y trocear playbooks (.md)

Crear embeddings y un índice FAISS

Recuperar contexto relevante para un mensaje

Características

Usa llm.openai_client inyectado

Usa llm.embedding_model

Cachea índices en disco

No crea clientes propios

Si no hay API key → devuelve contexto vacío (graceful)

Resultado

Devuelve texto contextual que se inyecta como:
[Playbook guidance]
...


4️⃣ ChatbotService

📍 Generación de respuesta conversacional

Responsabilidad

Construir instrucciones finales del modelo

Generar la respuesta del asistente

Clientes usados

llm.openai_client → si use_local = false

llm.lmstudio_client → si use_local = true

Qué recibe

message

history (sanitizado)

setting (fusionado con clasificación + RAG)

Qué NO hace

No clasifica emociones

No crea clientes

No accede a .env

6️⃣ AuthService

📍 Sesión y autenticación (cookie-based)

Responsabilidad

Leer la cookie de sesión (`COOKIE_NAME`, default `oms_session`)

Serializar/deserializar sesión con `SESSION_SECRET`

Exponer helpers:

`get_current_user(request)` → `dict | None` (no fuerza auth)

`require_auth(user)` → 401 si no hay usuario

Endpoint relacionado

`GET /api/me` → “me” fuerte (requiere auth, puede responder 401)

7️⃣ UsageService

📍 Límite de mensajes + cookie de invitado

Responsabilidad

Gestionar cookie invitado (`GUEST_COOKIE_NAME`, default `oms_guest`)

Contar turnos de usuario en `history`

Enforzar límites (paywall 402) para:

Anónimo → `ANON_MESSAGE_LIMIT` (default 10)

Autenticado → `AUTH_MESSAGE_LIMIT` (default 100)

5️⃣ main.py

📍 Orquestador limpio

Responsabilidad

Instanciar servicios una sola vez

Coordinar el flujo de /api/chat

Exponer endpoints “policy” sin forzar auth

Flujo típico

Recibe request del frontend

rag_context = rag.retrieve(message)

classification = classifier.classify(message)

Fusiona:

setting del frontend

hints de clasificación (sin pisar)

contexto RAG

response = chatbot.chat(...)

Devuelve:

{
  "response": "...",
  "model": "...",
  "classification": {...},
  "risk": "none"
}

Endpoints relacionados (auth + límites)

`GET /api/me/policy` → siempre 200, devuelve:

`isAuthenticated` + `maxMessages` + `limits{anon/auth}` (+ `user` opcional si logged)

`GET /api/me` → requiere auth (401 si no logged)

Ventajas

Fácil de leer

Fácil de testear

Fácil de extender (auth, DB, métricas)

🏗️ Esquema Visual (mental)


             ┌─────────────┐
             │ LLMSettings │
             │ (keys+LLMs) │
             └──────┬──────┘
                    │
     ┌──────────────┼──────────────┐
     │              │              │
┌────┼─────┐  ┌─────┼──────┐  ┌────┼─────────┐
│Classifier│  │ RagFaiss   │  │ Chatbot      │
│Service   │  │ Service    │  │ Service      │
└────┬─────┘  └────┬───────┘  └────┬─────────┘
     │             │               │
     └─────────────┼───────────────┘
                   │
              ┌────▼─────┐
              │ main.py  │
              │ Orquest. │
              └──────────┘

🎯 Beneficios de esta Arquitectura

✅ Cero duplicación de clientes

✅ Cero errores por .env en import-time

✅ Cloud y local conviven sin fricción

✅ Fácil añadir:

Claude

Fine-tuning

Autenticación

Persistencia

✅ Ideal para MVP → producción       

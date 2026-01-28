# OverMyShoulder Backend

FastAPI backend for OverMyShoulder.

## Run

```bash
uvicorn main:app --reload --port 8000
```

## Environment variables

LLM settings (used by `services/llmsettings.py`):

- `OPENAI_API_KEY` (required when `use_local=false`)
- `LMSTUDIO_BASE_URL` (default: `http://localhost:1234/v1`)
- `MODEL_OA` (default: `gpt-5-nano`)
- `MODEL_LM` (default: `openai/gpt-oss-20b`)

Other backend settings:

- `TOP_K` (default: `3`) – RAG top-k chunks
- `RESEND_API_KEY` – required for `/api/waitlist`
- `WAITLIST_NOTIFY_TO` – required for `/api/waitlist`
- `RESEND_FROM` (default: `OverMyShoulder <onboarding@resend.dev>`)

## Tests

```bash
pytest -q
```

## Architecture (summary)

Resumen rapido de componentes:

- `main.py`: FastAPI app, orquestacion de chat, clasificacion y RAG.
- `services/llmsettings.py`: carga de entorno y clientes compartidos.
- `services/service_chatbot.py`: chat puro con instrucciones.
- `services/service_classifier.py`: clasificacion via OpenAI Responses.
- `services/service_rag_faiss.py`: indice FAISS, cache y retrieval.
- `playbooks/`: fuentes para RAG.

See `arquitectura.md`.

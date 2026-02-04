
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
import resend

from services.llmsettings import LLMSettings
from services.service_chatbot import ChatbotService
from services.service_classifier import ClassifierService
from models.classifier import ClassifyResult
from services.service_rag_faiss import RagFaissService
from services.merge_setting import merge_setting

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

load_dotenv(override=True)
from services.service_auth import (  # noqa: E402
    DEBUG,
    GoogleAuthIn,
    auth_google as auth_google_handler,
    get_me as get_me_handler,
    get_current_user,
    logout as logout_handler,
    require_auth,
)

logger = logging.getLogger("main")

app = FastAPI()
llm = LLMSettings()
rag = RagFaissService(llm)
chatbot = ChatbotService(llm)
classifier = ClassifierService(llm)

# CORS
cors_origins = os.getenv("CORS_ORIGINS")
if cors_origins:
    allowed_origins = [origin.strip() for origin in cors_origins.split(",") if origin.strip()]
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://overmyshoulders.online",
        "https://www.overmyshoulders.online",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos de datos
class ChatRequest(BaseModel):
    message: str
    history: list = Field(default_factory=list)
    setting: dict = Field(default_factory=dict)
    use_local: bool = False  # True = LMStudio, False = GPT


@app.get("/")
def root():
    return {"status": "Backend running", "endpoints": ["/api/chat", "/api/classify", "/api/waitlist"]}

@app.get("/api/health")
def health():
    if rag._index is None:
        return {"status": "ok", "rag": "not_initialized"}
    return {"status": "ok", "rag": rag._index.status()}

@app.on_event("startup")
def startup_event():
    rag.build_or_load()


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        rag_context = rag.retrieve(request.message, top_k=3)
        logger.info("[RAG] used=%s len=%s", bool(rag_context), len(rag_context) if rag_context else 0)

        classification = classifier.classify(request.message)
        classification_payload = classification if isinstance(classification, dict) else dict(classification)

        merged_setting = merge_setting(
            request_setting=request.setting,
            classification=classification_payload,
            rag_context=rag_context,
        )

        response = chatbot.chat(
            message=request.message,
            history=request.history,
            setting=merged_setting,
            use_local=request.use_local
        )
        
        return {
            "response": response,
            "model": "LMStudio" if request.use_local else "OpenAI Responses",
            "classification": classification,
            "risk": classification.get("risk") if isinstance(classification, dict) else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ClassifyRequest(BaseModel):
    message: str
    history: list = Field(default_factory=list)
    setting: dict = Field(default_factory=dict)
    use_local: bool = False


@app.post("/api/classify", response_model=ClassifyResult)
async def classify(request: ClassifyRequest):
    try:
        result = classifier.classify(request.message)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/google")
def auth_google(payload: GoogleAuthIn):
    return auth_google_handler(payload)


@app.get("/api/me")
def get_me(user: dict = Depends(require_auth)):
    return get_me_handler(user)


@app.post("/api/logout")
def logout(response: Response):
    return logout_handler(response)
    

class WaitlistIn(BaseModel):
    email: EmailStr



@app.post("/api/waitlist")
def waitlist(payload: WaitlistIn):
        
    #resend.api_key = os.environ["RESEND_API_KEY"]
    key = os.getenv("RESEND_API_KEY")
    if not key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY missing")
    resend.api_key = key

    notify_to = os.getenv("WAITLIST_NOTIFY_TO")
    if not notify_to:
        raise HTTPException(status_code=500, detail="WAITLIST_NOTIFY_TO missing")

    #RESEND_FROM = os.getenv("RESEND_FROM")#, "OverMyShoulder <onboarding@tu-dominio.com>")# fallback DEV overmyshoulder.online,
    from_email = os.getenv("RESEND_FROM", "OverMyShoulder <onboarding@resend.dev>")        
        
        
    try:      
        resp = resend.Emails.send({
            "from":from_email,  
            "to": [notify_to],
            "subject": "Nueva waitlist - OverMyShoulder",
            "html": f"""
            <strong>Nuevo email en waitlist:</strong> {payload.email}
            <p><b>Origen:</b> Landing</p>
            <p><b>Timestamp:</b> {datetime.now(timezone.utc).isoformat()}</p>
            """,
        })
        return {"ok": True, "resend": resp }
    except Exception as e:
        # Devuelve la razón real al frontend
        raise HTTPException(status_code=500, detail=str(e))

#Debug

if DEBUG:
    class ChatSetting(BaseModel):
        state: str | None = None
        emotionalState: str | None = None
        tone: str | None = None

    class ChatIn(BaseModel):
        message: str
        history: list[dict] = []
        setting: ChatSetting = ChatSetting()

    @app.post("/api/chat-debug")
    def chat_debug(payload: ChatIn):
        # OJO: en prod no loguees contenido sensible
        return {
            "ok": True,
            "received_setting": payload.setting.model_dump(),
        }
    
# Para correr el servidor: uvicorn main:app --reload --port 8000

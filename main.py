
from datetime import datetime,timezone
import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
import resend

from services.llmsettings import LLMSettings
from services.service_chatbot import ChatbotService
from services.service_classifier import ClassifierService
from models.classifier import ClassifyResult
from services.service_rag_faiss import RagFaissService

load_dotenv(override=True)

app = FastAPI()
llm = LLMSettings()
rag = RagFaissService(llm)
chatbot = ChatbotService(llm)
classifier = ClassifierService(llm)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "http://127.0.0.1:5173",
                   "http://localhost:3000",
                   "http://127.0.0.1:3000",
                   ],  # Vite
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
        merged_setting = dict(request.setting or {})

        rag_context = rag.retrieve(request.message, top_k=3)
        if rag_context and "_rag_context" not in merged_setting and "rag_context" not in merged_setting:
            merged_setting["_rag_context"] = rag_context

        classification = classifier.classify(request.message)
        classification_payload = dict(classification)
        if merged_setting.get("emotionalState") or merged_setting.get("mood"):
            classification_payload.pop("mood", None)
        if merged_setting.get("tone"):
            classification_payload.pop("tone_hint", None)
        if merged_setting.get("mode"):
            classification_payload.pop("night_mode_hint", None)

        for key, value in classification_payload.items():
            if key not in merged_setting:
                merged_setting[key] = value
        if not merged_setting.get("tone") and classification.get("tone_hint"):
            merged_setting["tone"] = classification["tone_hint"]
        if not merged_setting.get("emotionalState") and not merged_setting.get("mood"):
            merged_setting["emotionalState"] = classification.get("mood")
        if not merged_setting.get("mode") and classification.get("night_mode_hint"):
            merged_setting["mode"] = "night"
        if (
            not merged_setting.get("night_mode")
            and not merged_setting.get("mode")
            and classification.get("night_mode_hint")
        ):
            merged_setting["night_mode"] = True

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

class ChatSetting(BaseModel):
    mode: Optional[str] = None
    emotionalState: Optional[str] = None
    tone: Optional[str] = None

class ChatIn(BaseModel):
    message: str
    history: List[Dict[str, Any]] = []
    setting: ChatSetting = ChatSetting()

@app.post("/api/chat-debug")
def chat_debug(payload: ChatIn):
    # OJO: en prod no loguees contenido sensible
    return {
        "ok": True,
        "received_setting": payload.setting.model_dump(),
    }
    
# Para correr el servidor: uvicorn main:app --reload --port 8000

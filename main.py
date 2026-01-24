
from datetime import datetime,timezone
import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
import resend

from chatbot import chat_oms
from models.classifier import ClassifyResult
from services.classifier_service import classify_oms

load_dotenv(override=True)

app = FastAPI()

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

@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        classification = classify_oms(
            message=request.message,
            history=request.history,
            setting=request.setting,
            use_local=request.use_local
        )

        user_setting = request.setting or {}
        def pick_user(value, fallback):
            return value if value not in (None, "") else fallback

        merged_setting = {
            "tone": pick_user(user_setting.get("tone"), classification.get("tone_hint")),
            "mood": classification.get("mood"),
            "night_mode": pick_user(user_setting.get("night_mode"), classification.get("night_mode_hint"))
        }

        response = chat_oms(
            message=request.message,
            history=request.history,
            setting=merged_setting,
            use_local=request.use_local
        )
        
        return {
            "response": response,
            "model": "LMStudio" if request.use_local else "OpenAI Responses",
            "classification": classification,
            "risk": classification.get("risk")
        }
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
        result = classify_oms(
            message=request.message,
            history=request.history,
            setting=request.setting,
            use_local=request.use_local
        )
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

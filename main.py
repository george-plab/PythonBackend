## Basic
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv(override=True)

## App core

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field


import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


## service App 

from services.llmsettings import LLMSettings
from services.service_chatbot import ChatbotService
from services.service_classifier import ClassifierService
from models.classifier import ClassifyResult
from services.service_rag_faiss import RagFaissService
from services.merge_setting import merge_setting
from services.service_auth import  GoogleAuthIn, AuthService
from services.service_usage import UsageService



app = FastAPI()
llm = LLMSettings()
rag = RagFaissService(llm)
chatbot = ChatbotService(llm)
classifier = ClassifierService(llm)
#auth_service: AuthService | None = None
#usage_service: UsageService | None = None
debug = os.getenv("DEBUG", "").lower() == "true"
anon_limit = int(os.getenv("ANON_MESSAGE_LIMIT", "10"))
auth_limit = int(os.getenv("AUTH_MESSAGE_LIMIT", "100"))
auth_service = AuthService(
        debug=debug,
        cookie_name=os.getenv("COOKIE_NAME","oms_session"),
        session_max_age_seconds=int( os.getenv( "SESSION_MAX_AGE_SECONDS","86400" ) ),
        )
usage_service = UsageService(
        debug=debug,
        guest_cookie_name=os.getenv("GUEST_COOKIE_NAME","oms_guest"),
        anon_message_limit=anon_limit,
        auth_message_limit=auth_limit,
    )

DEBUG=os.getenv("DEBUG", "").lower() == "true"



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


## API

@app.get("/")
def root():
    return {
        "status": "Backend running",
        "endpoints": [
            "/api/health",
            "/api/chat",
            "/api/classify",
            "/api/waitlist",
            "/api/auth/google",
            "/api/me",
            "/api/me/policy",
            "/api/logout",
        ],
        "docs": ["/docs", "/redoc", "/openapi.json"],
    }

@app.get("/api/health")
def health():
    if rag._index is None:
        return {"status": "ok", "rag": "not_initialized"}
    return {"status": "ok", "rag": rag._index.status()}


@app.on_event("startup") #Deprecated
def startup_event():
    print("Startup Event")
    rag.build_or_load()
    #global auth_service, usage_service
 

#@asynccontextmanager
#async def lifespan(app: FastAPI):
    # STARTUP
    #global auth_service
    #auth_service = AuthService()
    #yield
    # SHUTDOWN (si algún día necesitas cleanup)
    # auth_service.close()  # opcional

#app = FastAPI(lifespan=lifespan)

def _require_auth_service() -> AuthService:
    if auth_service is None:
        raise HTTPException(status_code=500, detail="AuthService not initialized")
    return auth_service

def _require_usage_service() -> UsageService:
    if usage_service is None:
        raise HTTPException(status_code=500, detail="UsageService not initialized")
    return usage_service

def get_current_user(request: Request) -> dict | None:
    return _require_auth_service().get_current_user(request)


def require_user(user: dict | None = Depends(get_current_user)) -> dict:
    return _require_auth_service().require_auth(user)




@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request):
    user: dict | None = None
    if auth_service is not None:
        user = auth_service.get_current_user(request)

    logger.info("cookies: %s", request.cookies)
    usage = _require_usage_service()
    user_turns = usage.count_user_turns(payload.history)
    
    is_anon = user is None
    if is_anon:        
        try:
            usage.enforce_anon_limit(user_turns)
        except HTTPException as exc:
            if exc.status_code == 402:
                paywall_resp = JSONResponse({"detail": exc.detail}, status_code=402)
                usage.ensure_guest_id(request, paywall_resp)
                return paywall_resp
            raise
    else:
        try:
           usage.enforce_auth_limit(user_turns)  # implementar
        except HTTPException as exc:
            if exc.status_code == 402:
                return JSONResponse({"detail": exc.detail}, status_code=402)
            raise
    try:
        rag_context = rag.retrieve(payload.message, top_k=3)
        logger.info("[RAG] used=%s len=%s", bool(rag_context), len(rag_context) if rag_context else 0)

        classification = classifier.classify(payload.message)
        classification_payload = classification if isinstance(classification, dict) else dict(classification)

        merged_setting = merge_setting(
            request_setting=payload.setting,
            classification=classification_payload,
            rag_context=rag_context,
        )

        chat_response = chatbot.chat(
            message=payload.message,
            history=payload.history,
            setting=merged_setting,
            use_local=payload.use_local
        )

        data = {
            "response": chat_response,
            "model": "LMStudio" if payload.use_local else "OpenAI Responses",
            "classification": classification,
            "risk": classification.get("risk") if isinstance(classification, dict) else None,
        }
        resp = JSONResponse(data)
        
        if is_anon:
            _require_usage_service().ensure_guest_id(request, resp)
        return resp
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
    return _require_auth_service().auth_google(payload)


@app.get("/api/me")
async def get_me(user: dict = Depends(require_user)):
    return _require_auth_service().get_me(user)

@app.get("/api/me/policy")
def get_me_policy(request: Request):
    user: dict | None = None
    if auth_service is not None:
        try:
            user = auth_service.get_current_user(request)
        except Exception:
            user = None

    is_authenticated = user is not None
    payload: dict = {
        "ok": True,
        "isAuthenticated": is_authenticated,
        "maxMessages": auth_limit if is_authenticated else anon_limit,
        "limits": {
            "anon": {"messages": anon_limit},
            "auth": {"messages": auth_limit},
        },
    }
    if is_authenticated:
        payload["user"] = {
            "email": user.get("email") if isinstance(user, dict) else None,
            "name": user.get("name") if isinstance(user, dict) else None,
            "picture": user.get("picture") if isinstance(user, dict) else None,
        }
    return payload


@app.post("/api/logout")
def logout(response: Response):
    #Para borrar cookies en local
    if DEBUG:
        response.delete_cookie(
            key="oms_session",
            path="/",
            samesite="lax",
        )
        response.delete_cookie(
            key="oms_guest",
            path="/",
            samesite="lax",
        )
        return {"ok": True} 
    else:
        #No se borra la session invitada 
        return _require_auth_service().logout(response)
    

class WaitlistIn(BaseModel):
    email: EmailStr



@app.post("/api/waitlist")
def waitlist(payload: WaitlistIn):
    import resend
        
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

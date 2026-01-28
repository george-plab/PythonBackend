
## Python file educational add to 
##add to .ignore

# import os
# import re
# from dotenv import load_dotenv
# from typing import Dict
# import requests
# from fastapi import FastAPI,APIRouter, HTTPException
# import resend
# from pydantic import BaseModel, EmailStr

# router = APIRouter()

# load_dotenv(override=True)
#resend.api_key = os.getenv['RESEND_API_KEY']


# app = FastAPI()
# @app.post("/")
# def send_mail() -> Dict:
#     params: resend.Emails.SendParams = {
#         "from": "Acme <onboarding@resend.dev>",
#         "to": ["vplasin@gmail.com"],
#         "subject": "hello world",
#         "html": "<strong>it works!</strong>",
#     }
#     email: resend.Emails.SendResponse = resend.Emails.send(params)
#     return email

# waitlist.py (o en main.py)


# RESEND_API_KEY = os.getenv("RESEND_API_KEY")
# RESEND_FROM = os.getenv("RESEND_FROM", "OverMyShoulder <onboarding@tu-dominio.com>")
# WAITLIST_NOTIFY_TO = os.getenv("WAITLIST_NOTIFY_TO", "tuemail@dominio.com")

# class WaitlistIn(BaseModel):
#     email: EmailStr

# @router.post("/api/waitlist")
# def waitlist(payload: WaitlistIn):
#     if not RESEND_API_KEY:
#         raise HTTPException(status_code=500, detail="RESEND_API_KEY missing")

#     # Email a ti (notificación)
#     r = requests.post(
#         "https://api.resend.com/emails",
#         headers={
#             "Authorization": f"Bearer {RESEND_API_KEY}",
#             "Content-Type": "application/json",
#         },
#         json={
#             "from": RESEND_FROM,
#             "to": [WAITLIST_NOTIFY_TO],
#             "subject": "Nueva waitlist - OverMyShoulder",
#             "html": f"<p>Nuevo email en waitlist: <b>{payload.email}</b></p>",
#         },
#         timeout=15,
#     )

#     if r.status_code >= 400:
#         raise HTTPException(status_code=502, detail=f"Resend error: {r.text}")

#     return {"ok": True}

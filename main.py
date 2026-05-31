from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import firebase_admin
from firebase_admin import credentials, messaging, db
import os
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase Admin
if not firebase_admin._apps:
    # On Render: use environment variable
    service_account = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if service_account:
        cred_dict = json.loads(service_account)
        cred = credentials.Certificate(cred_dict)
    else:
        # Local development: use file
        cred = credentials.Certificate("serviceAccount.json")

    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://board-app-cc85f-default-rtdb.europe-west1.firebasedatabase.app"
    })


# ─── Models ───────────────────────────────────────────────

class TokenRequest(BaseModel):
    userId: str
    token: str

class NotifyCardRequest(BaseModel):
    authorName: str
    cardText: Optional[str] = ""

class NotifyLikeRequest(BaseModel):
    cardAuthorId: str
    likerName: str
    cardText: Optional[str] = ""


# ─── Register FCM Token ───────────────────────────────────

@app.post("/register-token")
async def register_token(req: TokenRequest):
    """Save user's FCM token to Firebase DB"""
    try:
        ref = db.reference(f"fcm_tokens/{req.userId}")
        ref.set(req.token)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Notify all users: new card published ─────────────────

@app.post("/notify-card")
async def notify_card(req: NotifyCardRequest):
    """Send notification to all users when someone publishes a card"""
    try:
        tokens_ref = db.reference("fcm_tokens")
        tokens_data = tokens_ref.get()

        if not tokens_data:
            return {"ok": True, "sent": 0}

        tokens = list(tokens_data.values())
        text_preview = req.cardText[:60] + "..." if len(req.cardText) > 60 else req.cardText
        body = f'"{text_preview}"' if text_preview else "نشر بطاقة جديدة"

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(
                title=f"✦ {req.authorName} نشر بطاقة جديدة",
                body=body,
            ),
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    icon="/board_app/icon-192.png",
                ),
                fcm_options=messaging.WebpushFCMOptions(
                    link="https://belaledoor.github.io/board_app/"
                )
            )
        )

        response = messaging.send_each_for_multicast(message)
        return {"ok": True, "sent": response.success_count, "failed": response.failure_count}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Notify card owner: someone liked their card ──────────

@app.post("/notify-like")
async def notify_like(req: NotifyLikeRequest):
    """Send notification to card owner when someone likes their card"""
    try:
        token_ref = db.reference(f"fcm_tokens/{req.cardAuthorId}")
        token = token_ref.get()

        if not token:
            return {"ok": True, "sent": 0}

        text_preview = req.cardText[:40] + "..." if len(req.cardText) > 40 else req.cardText
        body = f'على بطاقتك "{text_preview}"' if text_preview else "على بطاقتك"

        message = messaging.Message(
            token=token,
            notification=messaging.Notification(
                title=f"❤️ {req.likerName} أعجبه منشورك",
                body=body,
            ),
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    icon="/board_app/icon-192.png",
                ),
                fcm_options=messaging.WebpushFCMOptions(
                    link="https://belaledoor.github.io/board_app/"
                )
            )
        )

        messaging.send(message)
        return {"ok": True, "sent": 1}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def root():
    return {"status": "BŌARD backend running ✦"}

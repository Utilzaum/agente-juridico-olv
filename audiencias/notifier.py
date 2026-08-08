"""Notificação console + Telegram (API pura via urllib).
Prioriza o Bot de Audiências (TELEGRAM_BOT_TOKEN_AUDIENCIA no .env)."""
import json
import os
import urllib.request

from dotenv import load_dotenv

load_dotenv()


def _cfg():
    token = (os.getenv("TELEGRAM_BOT_TOKEN_AUDIENCIA")
             or os.getenv("TELEGRAM_BOT_TOKEN_ORQUESTRADOR")
             or os.getenv("TELEGRAM_BOT_TOKEN_IA")
             or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID")
            or os.getenv("TELEGRAM_ADMIN_ID") or "").strip() or "501276610"
    return token, chat


def notificar(msg):
    print(msg, flush=True)
    token, chat = _cfg()
    if not token:
        return False
    try:
        req = urllib.request.Request(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            data=json.dumps({"chat_id": chat, "text": msg}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print("[notifier] falha Telegram:", e)
        return False

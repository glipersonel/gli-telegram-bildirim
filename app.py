from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import OrderedDict

from flask import Flask, jsonify, request


app = Flask(__name__)
_recent_events: OrderedDict[str, float] = OrderedDict()


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Eksik ortam değişkeni: {name}")
    return value


def _bot_token() -> str:
    """Tokeni kullanmadan önce doğrular; hatalarda tokeni loglara yazdırmaz."""
    token = _required_env("TELEGRAM_BOT_TOKEN")
    if not re.fullmatch(r"\d{5,}:[A-Za-z0-9_-]{20,}", token):
        raise RuntimeError("TELEGRAM_BOT_TOKEN biçimi geçersiz")
    return token


def _authorized() -> bool:
    expected = os.environ.get("RELAY_SHARED_SECRET", "").strip()
    supplied = request.headers.get("X-Relay-Secret", "")
    return bool(expected and hmac.compare_digest(expected, supplied))


def _remember_once(event_id: str) -> bool:
    """Aynı olayın ağ yeniden denemeleriyle iki kez gönderilmesini önler."""
    now = time.time()
    while _recent_events and next(iter(_recent_events.values())) < now - 86400:
        _recent_events.popitem(last=False)
    if event_id in _recent_events:
        return False
    _recent_events[event_id] = now
    while len(_recent_events) > 2000:
        _recent_events.popitem(last=False)
    return True


def _telegram_call(method: str, data: dict) -> dict:
    token = _bot_token()
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def _telegram_send(text: str) -> dict:
    return _telegram_call("sendMessage", {
        "chat_id": _required_env("TELEGRAM_TEST_CHAT_ID"),
        "text": text,
        "disable_web_page_preview": True,
    })


@app.get("/")
@app.get("/health")
def health():
    return jsonify(ok=True, service="gli-telegram-relay", test_mode=True)


@app.post("/notify")
def notify():
    if not _authorized():
        return jsonify(ok=False, error="unauthorized"), 401
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()[:200]
    message = str(data.get("message", "")).strip()[:3500]
    event_type = str(data.get("event_type", "notification")).strip()[:80]
    event_id = str(data.get("event_id", "")).strip()[:160]
    if not title or not message:
        return jsonify(ok=False, error="title_and_message_required"), 400
    if not event_id:
        raw = f"{event_type}|{title}|{message}".encode("utf-8")
        event_id = hashlib.sha256(raw).hexdigest()
    if not _remember_once(event_id):
        return jsonify(ok=True, duplicate=True, test_mode=True)
    text = f"🧪 TEST MODU\n\n{title}\n{message}"
    try:
        result = _telegram_send(text)
    except (RuntimeError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        _recent_events.pop(event_id, None)
        return jsonify(ok=False, error=str(exc)), 502
    return jsonify(ok=bool(result.get("ok")), test_mode=True)


@app.get("/updates")
def updates():
    """Telegram mesajlarını yalnız TEST hesabı için V1.82'ye aktarır."""
    if not _authorized():
        return jsonify(ok=False, error="unauthorized"), 401
    try:
        offset = max(0, int(request.args.get("offset", "0")))
    except ValueError:
        return jsonify(ok=False, error="invalid_offset"), 400
    try:
        result = _telegram_call("getUpdates", {
            "offset": offset,
            "limit": 50,
            "timeout": 0,
            "allowed_updates": ["message"],
        })
    except (RuntimeError, urllib.error.URLError, TimeoutError, ValueError):
        return jsonify(ok=False, error="telegram_updates_failed"), 502

    test_chat_id = _required_env("TELEGRAM_TEST_CHAT_ID")
    temiz = []
    next_offset = offset
    for update in result.get("result", []):
        update_id = int(update.get("update_id", 0))
        next_offset = max(next_offset, update_id + 1)
        message = update.get("message") or {}
        chat = message.get("chat") or {}
        if str(chat.get("id", "")) != test_chat_id:
            continue
        sender = message.get("from") or {}
        text = str(message.get("text", "")).strip()
        if not text:
            continue
        temiz.append({
            "update_id": update_id,
            "chat_id": str(chat.get("id", "")),
            "text": text[:2000],
            "username": str(sender.get("username", ""))[:80],
            "first_name": str(sender.get("first_name", ""))[:80],
            "date": int(message.get("date", 0)),
        })
    return jsonify(ok=True, updates=temiz, next_offset=next_offset, test_mode=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))

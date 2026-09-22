from __future__ import annotations

import hashlib
import hmac
import json
import os
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


def _telegram_send(text: str) -> dict:
    token = _required_env("TELEGRAM_BOT_TOKEN")
    chat_id = _required_env("TELEGRAM_TEST_CHAT_ID")
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))

"""WB.Track — API на Flask для PythonAnywhere.

Особенности площадки: исходящий интернет ограничен белым списком, поэтому
wbbasket.ru с сервера недоступен. Значит сервер НЕ тянет товары сам, а
принимает название и цены от клиента (приложение или воркер GitHub Actions).

Совместимость: старый APK ходит без токена (?user=логин) — такой запрос
обслуживается, но помечается как неаутентифицированный. Как только будет
установлена сборка с токеном, можно включить REQUIRE_TOKEN=1.
"""

import hashlib
import hmac
import json
import os
import random
import requests
import secrets
import sys
import threading
import time

from flask import Flask, request, jsonify

app = Flask(__name__)
HERE = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.environ.get("TASKS_FILE") or os.path.join(HERE, "tasks.json")
USERS_FILE = os.environ.get("USERS_FILE") or os.path.join(HERE, "users.json")
CODES_FILE = os.environ.get("CODES_FILE") or os.path.join(HERE, "codes.json")
CODE_TTL = 300
TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
S = "/"

def tg_url(method):
    return "https://api.telegram.org/bot%s/%s" % (TG_TOKEN, method)
UI_FILE = os.path.join(HERE, "app_ui.py")
REQUIRE_TOKEN = os.environ.get("REQUIRE_TOKEN", "").lower() in ("1", "true", "yes")

PBKDF2_ITERATIONS = 200_000
_lock = threading.Lock()


def _load_dotenv(path=os.path.join(HERE, ".env")):
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip(), val.strip().strip("\"'")
                if not key:
                    continue
                if os.environ.get(key, "").strip() == "":
                    os.environ[key] = val
    except OSError as e:
        print("Не удалось прочитать .env: %s" % e)


_load_dotenv()

REQUIRE_TOKEN = os.environ.get("REQUIRE_TOKEN", "").lower() in ("1", "true", "yes")


# ------------------------------------------------------------------ хранилище

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# -------------------------------------------------------------------- пароли

def hash_pw(password, salt=None):
    salt = salt or secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), PBKDF2_ITERATIONS)
    return "pbkdf2$%d$%s$%s" % (PBKDF2_ITERATIONS, salt, digest.hex())


def check_pw(stored, password):
    if not stored:
        return False
    if stored.startswith("pbkdf2$"):
        try:
            _, iterations, salt, expected = stored.split("$")
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations))
            return hmac.compare_digest(digest.hex(), expected)
        except (ValueError, TypeError):
            return False
    # старый формат: sha256 без соли
    return hmac.compare_digest(stored, hashlib.sha256(password.encode("utf-8")).hexdigest())


def send_tg(chat_id, text):
    if not TG_TOKEN:
        return {"ok": False, "error": "TG_TOKEN empty on server"}
    try:
        r = requests.post(tg_url("sendMessage"), json={"chat_id": chat_id, "text": text}, timeout=10)
        if r.status_code != 200:
            return {"ok": False, "error": "HTTP %s: %s" % (r.status_code, r.text[:200])}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


def new_token():
    return secrets.token_urlsafe(24)


# ------------------------------------------------------------- аутентификация

def bearer_token():
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def find_user_by_token(token):
    if not token:
        return None, None
    users = load_json(USERS_FILE, {})
    for login, user in users.items():
        saved = user.get("token")
        if saved and hmac.compare_digest(saved, token):
            return login, user
    return None, None


def resolve_owner(payload_user="default"):
    """Кто выполняет запрос: токен важнее поля owner/user в запросе."""
    login, _ = find_user_by_token(bearer_token())
    if login:
        return login, True
    if REQUIRE_TOKEN:
        return None, False
    return (payload_user or "default").strip().lower(), False


def unauthorized():
    return jsonify({"ok": False, "error": "Требуется авторизация"}), 401


# --------------------------------------------------------------------- товары

def normalize_task(item, previous=None):
    task = {
        "owner": item.get("owner") or (previous or {}).get("owner") or "default",
        "sku": int(item["sku"]),
        "target_price": int(item.get("target_price") or (previous or {}).get("target_price") or 0),
        "limit": max(1, int(item.get("limit") or (previous or {}).get("limit") or 1)),
        "bought": int((previous or {}).get("bought", 0)),
        "name": item.get("name") or (previous or {}).get("name") or "Товар %s" % item["sku"],
        "image": item.get("image") or (previous or {}).get("image") or "",
        "current_sbp": item.get("current_sbp", (previous or {}).get("current_sbp")),
        "current_wallet": item.get("current_wallet", (previous or {}).get("current_wallet")),
    }
    if "bought" in item:
        task["bought"] = int(item["bought"])
    return task


# -------------------------------------------------------------------- маршруты

@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
def index():
    return jsonify({"status": "ok", "service": "WB.Track API", "require_token": REQUIRE_TOKEN, "tg_token_set": bool(TG_TOKEN), "tg_token_len": len(TG_TOKEN), "dotenv_path": os.path.join(HERE, ".env"), "dotenv_exists": os.path.exists(os.path.join(HERE, ".env"))})


@app.route("/get_ui", methods=["GET"])
def get_ui():
    """Оставлено для совместимости со старыми сборками."""
    if not os.path.exists(UI_FILE):
        return "", 404
    with open(UI_FILE, "r", encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/register", methods=["POST"])
def register():
    data = request.json or {}
    login = (data.get("login") or "").strip().lower()
    password = (data.get("password") or "").strip()
    tg_id = (data.get("tg_id") or "").strip()
    if len(login) < 3 or len(password) < 4:
        return jsonify({"ok": False, "error": "Логин от 3 символов, пароль от 4"}), 400
    with _lock:
        users = load_json(USERS_FILE, {})
        if login in users:
            return jsonify({"ok": False, "error": "Этот логин уже занят"}), 400
        token = new_token()
        users[login] = {"password": hash_pw(password), "tg_id": tg_id, "token": token}
        save_json(USERS_FILE, users)
    return jsonify({"ok": True, "login": login, "tg_id": tg_id, "token": token})


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    login = (data.get("login") or "").strip().lower()
    password = (data.get("password") or "").strip()
    users = load_json(USERS_FILE, {})
    user = users.get(login)
    if not user or not check_pw(user.get("password", ""), password):
        return jsonify({"ok": False, "error": "Неверный логин или пароль"}), 401

    token = user.get("token") or new_token()
    upgrade = not user.get("password", "").startswith("pbkdf2$") or user.get("token") != token
    if upgrade:
        with _lock:
            users = load_json(USERS_FILE, {})
            users[login] = dict(users.get(login) or user)
            users[login]["password"] = hash_pw(password)  # миграция со старого sha256
            users[login]["token"] = token
            save_json(USERS_FILE, users)
    return jsonify({"ok": True, "login": login, "tg_id": user.get("tg_id", ""), "token": token})


@app.route("/change_password", methods=["POST"])
def change_password():
    data = request.json or {}
    login, _ = find_user_by_token(bearer_token())
    if not login:
        login = (data.get("user") or "").strip().lower()
    users = load_json(USERS_FILE, {})
    user = users.get(login)
    if not user:
        return jsonify({"ok": False, "error": "Пользователь не найден"}), 404
    if not check_pw(user.get("password", ""), (data.get("old_password") or "").strip()):
        return jsonify({"ok": False, "error": "Неверный пароль"}), 401
    new_pw = (data.get("new_password") or "").strip()
    if len(new_pw) < 4:
        return jsonify({"ok": False, "error": "Новый пароль от 4 символов"}), 400
    with _lock:
        users = load_json(USERS_FILE, {})
        if login not in users:
            return jsonify({"ok": False, "error": "Пользователь не найден"}), 404
        users[login]["password"] = hash_pw(new_pw)
        save_json(USERS_FILE, users)
    return jsonify({"ok": True})


@app.route("/request_code", methods=["POST"])
def request_code():
    data = request.json or {}
    sys.stderr.write("request_code called: %r\\n" % (data,))
    sys.stderr.flush()
    raw = (data.get("tg_id") or "").strip()
    if raw.startswith("@"):
        chat, key = raw, raw[1:]
    elif raw.isdigit():
        chat, key = raw, raw
    else:
        chat, key = "@" + raw, raw
    if not key:
        return jsonify({"ok": False, "error": "Введите логин или ID Telegram"}), 400
    code = "%06d" % random.randrange(1000000)
    now = int(time.time())
    with _lock:
        codes = load_json(CODES_FILE, {})
        codes[key] = {"code": code, "expires": now + CODE_TTL}
        save_json(CODES_FILE, codes)
    result = send_tg(chat, "Код входа в WB.Track: %s (действует 5 минут)" % code)
    if not result.get("ok"):
        sys.stderr.write("request_code send failed: %s\\n" % (result.get("error"),))
        sys.stderr.flush()
    return jsonify({"ok": True, "sent": result.get("ok", False), "send_error": result.get("error")})


@app.route("/verify_code", methods=["POST"])
def verify_code():
    data = request.json or {}
    raw = (data.get("tg_id") or "").strip()
    if raw.startswith("@"):
        key = raw[1:]
    elif raw.isdigit():
        key = raw
    else:
        key = raw
    code = (data.get("code") or "").strip()
    now = int(time.time())
    with _lock:
        codes = load_json(CODES_FILE, {})
        entry = codes.get(key)
        if not entry or entry.get("code") != code or int(entry.get("expires", 0)) < now:
            return jsonify({"ok": False, "error": "Неверный или просроченный код"}), 401
        del codes[key]
        save_json(CODES_FILE, codes)
    login = "tg_" + key
    with _lock:
        users = load_json(USERS_FILE, {})
        if login not in users:
            users[login] = {"password": hash_pw(secrets.token_hex(16)), "tg_id": key, "token": new_token()}
        else:
            if not users[login].get("token"):
                users[login]["token"] = new_token()
            users[login]["tg_id"] = key
        save_json(USERS_FILE, users)
        token = users[login]["token"]
    return jsonify({"ok": True, "login": login, "tg_id": key, "token": token})


@app.route("/tasks", methods=["GET"])
def get_tasks():
    if request.args.get("all") in ("1", "true"):
        expected = os.environ.get("WORKER_TOKEN", "").strip()
        if expected and not hmac.compare_digest(expected, request.headers.get("X-Worker-Token", "")):
            return unauthorized()
        return jsonify(load_json(DATA_FILE, []))
    owner, _ = resolve_owner(request.args.get("user", "default"))
    if owner is None:
        return unauthorized()
    tasks = load_json(DATA_FILE, [])
    return jsonify([t for t in tasks if (t.get("owner") or "default") == owner])


@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.json or {}
    try:
        sku = int(data["sku"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"ok": False, "error": "Нужен sku"}), 400

    owner, _ = resolve_owner(data.get("owner", "default"))
    if owner is None:
        return unauthorized()

    with _lock:
        tasks = load_json(DATA_FILE, [])
        previous = next((t for t in tasks if (t.get("owner") or "default") == owner and int(t["sku"]) == sku), None)
        task = normalize_task(dict(data, owner=owner, sku=sku), previous)
        tasks = [t for t in tasks if not ((t.get("owner") or "default") == owner and int(t["sku"]) == sku)]
        tasks.append(task)
        save_json(DATA_FILE, tasks)
    return jsonify({"ok": True, "task": task})


@app.route("/tasks/<int:sku>", methods=["DELETE"])
def delete_task(sku):
    owner, _ = resolve_owner(request.args.get("user", "default"))
    if owner is None:
        return unauthorized()
    with _lock:
        tasks = load_json(DATA_FILE, [])
        left = [t for t in tasks if not ((t.get("owner") or "default") == owner and int(t["sku"]) == sku)]
        if len(left) == len(tasks):
            return jsonify({"ok": False, "error": "Задача не найдена"}), 404
        save_json(DATA_FILE, left)
    return jsonify({"ok": True, "status": "deleted"})


@app.route("/check_now", methods=["GET", "POST"])
def check_now():
    """Принудительная проверка. С PythonAnywhere WB недоступен — вернёт то, что было."""
    from wb_common import fetch_product  # импорт внутри: без модуля сервер всё равно поднимется

    owner, _ = resolve_owner(request.args.get("user", "default"))
    if owner is None:
        return unauthorized()

    updated = 0
    with _lock:
        tasks = load_json(DATA_FILE, [])
        for task in tasks:
            if (task.get("owner") or "default") != owner:
                continue
            if int(task.get("bought") or 0) >= int(task.get("limit") or 1):
                continue
            name, wallet, sbp, image = fetch_product(int(task["sku"]), timeout=5)
            if sbp is None:
                continue
            task["name"], task["current_wallet"], task["current_sbp"], task["image"] = name, wallet, sbp, image
            updated += 1
        if updated:
            save_json(DATA_FILE, tasks)
    return jsonify({"ok": True, "updated": updated})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)

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
CONTACTS_FILE = os.environ.get("CONTACTS_FILE") or os.path.join(HERE, "contacts.json")
LOGINS_FILE = os.environ.get("LOGINS_FILE") or os.path.join(HERE, "logins.json")
HISTORY_FILE = os.environ.get("HISTORY_FILE") or os.path.join(HERE, "history.json")
META_FILE = os.environ.get("META_FILE") or os.path.join(HERE, "meta.json")
CODE_TTL = 300
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
TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
BOT_LINK = os.environ.get("BOT_LINK") or "@wb_jekich_bot"
TG_SECRET = os.environ.get("TG_WEBHOOK_SECRET", "").strip()


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


def _save_contacts(contacts):
    try:
        save_json(CONTACTS_FILE, contacts)
    except OSError as e:
        sys.stderr.write("contacts save failed: %r\n" % (e,))


def _username_by_id(contacts, cid):
    for uname, info in contacts.items():
        if str(info.get("id")) == str(cid):
            return uname
    return ""


def peek_updates():
    """Неподтверждённые апдейты бота (offset не двигаем, воркер не страдает)."""
    if not TG_TOKEN:
        return []
    try:
        r = requests.get(tg_url("getUpdates"), params={"limit": 100, "timeout": 0}, timeout=10)
        payload = r.json()
    except Exception:
        return []
    return (payload.get("result") or []) if isinstance(payload, dict) else []


def peek_start_nonces():
    """nonce из '/start <nonce>' -> {id, username}."""
    found = {}
    for upd in peek_updates():
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        text = (msg.get("text") or "").strip()
        if chat.get("type") != "private" or not chat.get("id"):
            continue
        parts = text.split()
        if len(parts) >= 2 and parts[0].lower().split("@")[0] == "/start":
            found[parts[1]] = {"id": str(chat["id"]), "username": (chat.get("username") or "").strip().lower()}
    return found


def peek_contacts():
    """Запоминает username -> id из неподтверждённых апдейтов (offset не двигаем)."""
    found = {}
    for upd in peek_updates():
        msg = upd.get("message") or upd.get("edited_message") or upd.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private":
            continue
        uname = (chat.get("username") or "").strip().lower()
        cid = chat.get("id")
        if uname and cid is not None:
            found[uname] = {"id": str(cid), "name": chat.get("first_name") or ""}
    return found


def resolve_chat(raw):
    """(chat_id, key, error). Логин (@username) — основной способ, id — запасной."""
    raw = (raw or "").strip()
    if not raw:
        return "", "", "Введите логин Telegram (например @yurev0) или числовой ID"
    if not TG_TOKEN:
        return "", raw, "TG_TOKEN empty on server"
    handle = (raw[1:] if raw.startswith("@") else raw).strip()
    if not handle:
        return "", "", "Введите логин Telegram"
    contacts = load_json(CONTACTS_FILE, {}) or {}
    if handle.isdigit():
        uname = _username_by_id(contacts, handle)
        return handle, (uname or handle), None
    uname = handle.lower()
    info = contacts.get(uname)
    if not info:
        fresh = peek_contacts()
        if fresh:
            contacts.update(fresh)
            _save_contacts(contacts)
            info = contacts.get(uname)
    if info and info.get("id"):
        return str(info["id"]), uname, None
    # незнакомый логин: возможно, это канал/группа, либо человек ещё не жал Start
    try:
        r = requests.get(tg_url("getChat"), params={"chat_id": "@" + uname}, timeout=10)
        if r.status_code == 200:
            res = r.json().get("result") or {}
            if res.get("type") in ("channel", "group", "supergroup"):
                return "", uname, "@%s — это канал или группа. Введите свой личный логин." % handle
            if res.get("type") == "private" and res.get("id") is not None:
                contacts[uname] = {"id": str(res["id"]), "name": res.get("first_name") or ""}
                _save_contacts(contacts)
                return str(res["id"]), uname, None
    except Exception as e:
        sys.stderr.write("getChat error: %r\n" % (e,))
    # пользователь мог только что нажать Start — пробуем ещё раз
    fresh = peek_contacts()
    if fresh:
        contacts.update(fresh)
        _save_contacts(contacts)
        if uname in contacts and contacts[uname].get("id"):
            return str(contacts[uname]["id"]), uname, None
    return "", uname, "Аккаунт @%s ещё не открывал бота. Откройте %s в Telegram, нажмите Start и повторите." % (handle, BOT_LINK)


def send_tg(chat_id, text, markup=None):
    if not TG_TOKEN:
        return {"ok": False, "error": "TG_TOKEN empty on server"}
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if markup:
        payload["reply_markup"] = markup
    try:
        r = requests.post(tg_url("sendMessage"), json=payload, timeout=10)
        if r.status_code != 200:
            return {"ok": False, "error": "HTTP %s: %s" % (r.status_code, r.text[:200])}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": repr(e)}


HELP_TEXT = (
    "🤖 WB.Track\n"
    "Отправьте: АРТИКУЛ ЦЕНА [КОЛИЧЕСТВО]\n"
    "Пример: 596432419 420\n\n"
    "/list — задачи\n"
    "/del АРТИКУЛ — удалить"
)


def _tg_tasks(owner="telegram"):
    tasks = load_json(DATA_FILE, [])
    return [t for t in tasks if (t.get("owner") or "default") == owner]


def _tg_list(owner):
    tasks = _tg_tasks(owner)
    if not tasks:
        return "📭 Список пуст."
    lines = ["📋 Задачи:"]
    for t in tasks:
        cur = ("%s ₽" % t["current_sbp"]) if t.get("current_sbp") else "—"
        lines.append("%s (арт. %s)\nСейчас: %s | Цель: до %s ₽ | %d/%d"
                     % (t.get("name") or t["sku"], t["sku"], cur, t["target_price"],
                        int(t.get("bought") or 0), int(t.get("limit") or 1)))
    return "\n\n".join(lines)


def _tg_add(owner, text):
    nums = [int(p) for p in text.replace(",", " ").split() if p.strip().isdigit()]
    if len(nums) < 2:
        return "⚠️ Формат: АРТИКУЛ ЦЕНА (например: 596432419 420)"
    sku, price = nums[0], nums[1]
    limit = max(1, nums[2]) if len(nums) > 2 else 1
    with _lock:
        tasks = load_json(DATA_FILE, [])
        prev = next((t for t in tasks if (t.get("owner") or "default") == owner and int(t["sku"]) == sku), None)
        task = normalize_task({"owner": owner, "sku": sku, "target_price": price, "limit": limit}, prev)
        tasks = [t for t in tasks if not ((t.get("owner") or "default") == owner and int(t["sku"]) == sku)]
        tasks.append(task)
        save_json(DATA_FILE, tasks)
    return "✅ Добавлено: %s\nЦель: до %s ₽ | Кол-во: %d" % (task["name"], price, limit)


def _tg_del(owner, text):
    nums = [int(p) for p in text.replace(",", " ").split() if p.strip().isdigit()]
    if not nums:
        return "⚠️ Формат: /del АРТИКУЛ"
    sku = nums[0]
    with _lock:
        tasks = load_json(DATA_FILE, [])
        left = [t for t in tasks if not ((t.get("owner") or "default") == owner and int(t["sku"]) == sku)]
        if len(left) == len(tasks):
            return "🤷 Нет задачи с артикулом %s" % sku
        save_json(DATA_FILE, left)
    return "🗑 Удалено: %s" % sku


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
    expected = os.environ.get("WORKER_TOKEN", "").strip()
    if expected and hmac.compare_digest(expected, request.headers.get("X-Worker-Token", "")):
        return (payload_user or "default").strip().lower(), False
    if REQUIRE_TOKEN:
        return None, False
    return (payload_user or "default").strip().lower(), False


def unauthorized():
    return jsonify({"ok": False, "error": "Требуется авторизация"}), 401


# --------------------------------------------------------------------- товары

def _hist_key(owner, sku):
    return "%s|%s" % (owner or "default", int(sku))


def append_history(owner, sku, price):
    """Пишет точку цены, если она изменилась или прошло больше 6 часов."""
    try:
        price = int(price)
    except (TypeError, ValueError):
        return
    if price <= 0:
        return
    now = int(time.time())
    key = _hist_key(owner, sku)
    hist = load_json(HISTORY_FILE, {}) or {}
    points = hist.get(key) or []
    last = points[-1] if points else None
    if last and int(last.get("p", 0)) == price and now - int(last.get("t", 0)) < 21600:
        return
    points.append({"t": now, "p": price})
    hist[key] = points[-400:]
    save_json(HISTORY_FILE, hist)


def history_prices(owner, sku, limit=40):
    points = (load_json(HISTORY_FILE, {}) or {}).get(_hist_key(owner, sku)) or []
    return [int(p.get("p", 0)) for p in points[-limit:] if p.get("p")]


def touch_last_check():
    try:
        meta = load_json(META_FILE, {}) or {}
        meta["last_check"] = int(time.time())
        save_json(META_FILE, meta)
    except OSError:
        pass


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
    return jsonify({"status": "ok", "service": "WB.Track API", "require_token": REQUIRE_TOKEN,
                    "last_check": int((load_json(META_FILE, {}) or {}).get("last_check") or 0)})


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
    chat, key, err = resolve_chat(raw)
    if err:
        return jsonify({"ok": False, "error": err, "sent": False}), 400
    code = "%06d" % random.randrange(1000000)
    now = int(time.time())
    keys = [key]
    if chat.isdigit() and chat not in keys:
        keys.append(chat)
    with _lock:
        codes = load_json(CODES_FILE, {})
        for k in keys:
            codes[k] = {"code": code, "expires": now + CODE_TTL}
        save_json(CODES_FILE, codes)
    result = send_tg(chat, "Код входа в WB.Track: %s (действует 5 минут)" % code)
    if not result.get("ok"):
        sys.stderr.write("request_code send failed: %s\\n" % (result.get("error"),))
        sys.stderr.flush()
        return jsonify({"ok": True, "sent": False, "send_error": result.get("error"),
                        "error": "Telegram не принял сообщение. Откройте %s, нажмите Start и повторите." % BOT_LINK})
    return jsonify({"ok": True, "sent": True})


@app.route("/tg_contact", methods=["POST"])
def tg_contact():
    """Воркер сообщает серверу: этот @username = этот telegram id."""
    expected = os.environ.get("WORKER_TOKEN", "").strip()
    if expected and not hmac.compare_digest(expected, request.headers.get("X-Worker-Token", "")):
        return unauthorized()
    data = request.json or {}
    uname = (data.get("username") or "").strip().lower().lstrip("@")
    cid = str(data.get("id") or "").strip()
    if not uname or not cid:
        return jsonify({"ok": False, "error": "username and id are required"}), 400
    with _lock:
        contacts = load_json(CONTACTS_FILE, {}) or {}
        contacts[uname] = {"id": cid, "name": (data.get("name") or "").strip()}
        _save_contacts(contacts)
    return jsonify({"ok": True})


def issue_token(tg_key, tg_id):
    """Создаёт/возвращает аккаунт и токен для telegram-пользователя."""
    login = "tg_" + tg_key
    with _lock:
        users = load_json(USERS_FILE, {})
        user = users.get(login)
        if user is None:
            user = {"password": hash_pw(secrets.token_hex(16)), "tg_id": tg_id, "token": new_token()}
            users[login] = user
        else:
            if not user.get("token"):
                user["token"] = new_token()
            user["tg_id"] = tg_id
        save_json(USERS_FILE, users)
    return user["token"], login


def _complete_login(nonce, cid, chat):
    """Привязывает ожидающий вход к telegram-id и запоминает username."""
    uname = (chat.get("username") or "").strip().lower()
    with _lock:
        if nonce:
            logins = load_json(LOGINS_FILE, {})
            entry = logins.get(nonce) or {"created": int(time.time())}
            entry.update({"id": str(cid), "username": uname})
            logins[nonce] = entry
            save_json(LOGINS_FILE, logins)
        if uname:
            contacts = load_json(CONTACTS_FILE, {}) or {}
            contacts[uname] = {"id": str(cid), "name": chat.get("first_name") or ""}
            _save_contacts(contacts)


@app.route("/start_login", methods=["POST"])
def start_login():
    """Приложение просит nonce, открывает бота и ждёт /poll_login."""
    nonce = secrets.token_urlsafe(9)
    now = int(time.time())
    with _lock:
        logins = load_json(LOGINS_FILE, {})
        logins = {k: v for k, v in logins.items() if now - int(v.get("created", 0)) < 900}
        logins[nonce] = {"created": now}
        save_json(LOGINS_FILE, logins)
    return jsonify({"ok": True, "nonce": nonce, "bot": BOT_LINK, "url": "https://t.me/%s?start=%s" % (BOT_LINK.lstrip("@"), nonce)})


@app.route("/poll_login", methods=["GET"])
def poll_login():
    """Ждём, пока человек нажмёт Start в боте. Тогда сразу вход без кода."""
    nonce = (request.args.get("nonce") or "").strip()
    if not nonce:
        return jsonify({"ok": False, "error": "nonce required"}), 400
    now = int(time.time())
    with _lock:
        entry = load_json(LOGINS_FILE, {}).get(nonce)
    if not entry or now - int(entry.get("created", 0)) > 900:
        return jsonify({"ok": False, "error": "expired"}), 400
    if not entry.get("id"):
        found = peek_start_nonces().get(nonce)
        if found:
            entry.update(found)
            with _lock:
                logins = load_json(LOGINS_FILE, {})
                logins[nonce] = entry
                save_json(LOGINS_FILE, logins)
            if found.get("username"):
                with _lock:
                    contacts = load_json(CONTACTS_FILE, {}) or {}
                    contacts[found["username"]] = {"id": found["id"], "name": ""}
                    _save_contacts(contacts)
    if not entry.get("id"):
        return jsonify({"ok": False, "pending": True})
    tg_key = entry.get("username") or str(entry["id"])
    token, login = issue_token(tg_key, entry["id"])
    return jsonify({"ok": True, "login": login, "token": token, "tg_id": entry.get("username") or entry["id"]})


@app.route("/tg_hook_8f3ka9qz", methods=["POST"])
def tg_webhook():
    """Сюда Telegram присылает сообщения бота — ответ мгновенный, без cron."""
    if TG_SECRET:
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(got, TG_SECRET):
            return "", 403
    upd = request.json or {}
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat") or {}
    text = (msg.get("text") or "").strip()
    cid = chat.get("id")
    if not cid:
        return jsonify({"ok": True})
    if chat.get("type") == "private" and chat.get("username"):
        with _lock:
            contacts = load_json(CONTACTS_FILE, {}) or {}
            contacts[chat["username"].strip().lower()] = {"id": str(cid), "name": chat.get("first_name") or ""}
            _save_contacts(contacts)
    parts = text.split()
    cmd = parts[0].lower().split("@")[0] if parts else ""
    owner = "telegram"
    if cmd == "/start":
        if len(parts) >= 2:
            _complete_login(parts[1], cid, chat)
        send_tg(cid, HELP_TEXT)
    elif cmd == "/help":
        send_tg(cid, HELP_TEXT)
    elif cmd == "/list":
        send_tg(cid, _tg_list(owner))
    elif cmd == "/del":
        send_tg(cid, _tg_del(owner, text))
    elif text:
        send_tg(cid, _tg_add(owner, text))
    return jsonify({"ok": True})


@app.route("/tg_start", methods=["POST"])
def tg_start():
    """Воркер увидел '/start <nonce>' — закрываем ожидающий вход."""
    expected = os.environ.get("WORKER_TOKEN", "").strip()
    if expected and not hmac.compare_digest(expected, request.headers.get("X-Worker-Token", "")):
        return unauthorized()
    data = request.json or {}
    nonce = (data.get("nonce") or "").strip()
    cid = str(data.get("id") or "").strip()
    if not nonce or not cid:
        return jsonify({"ok": False, "error": "nonce and id are required"}), 400
    uname = (data.get("username") or "").strip().lower().lstrip("@")
    with _lock:
        logins = load_json(LOGINS_FILE, {})
        entry = logins.get(nonce) or {"created": int(time.time())}
        entry.update({"id": cid, "username": uname})
        logins[nonce] = entry
        save_json(LOGINS_FILE, logins)
        if uname:
            contacts = load_json(CONTACTS_FILE, {}) or {}
            contacts[uname] = {"id": cid, "name": (data.get("name") or "").strip()}
            _save_contacts(contacts)
    return jsonify({"ok": True})


@app.route("/verify_code", methods=["POST"])
def verify_code():
    data = request.json or {}
    raw = (data.get("tg_id") or "").strip()
    key = raw[1:] if raw.startswith("@") else raw
    chat, ckey, _err = resolve_chat(raw) if TG_TOKEN else (raw, key, None)
    keys = [ckey or key]
    for extra in (key, chat):
        if extra and extra not in keys:
            keys.append(extra)
    code = (data.get("code") or "").strip()
    now = int(time.time())
    with _lock:
        codes = load_json(CODES_FILE, {})
        entry = None
        for k in keys:
            e = codes.get(k)
            if e and e.get("code") == code and int(e.get("expires", 0)) >= now:
                entry = e
                break
        if entry is None:
            return jsonify({"ok": False, "error": "Неверный или просроченный код"}), 401
        for k in keys:
            codes.pop(k, None)
        save_json(CODES_FILE, codes)
    login_key = keys[0]
    token, login = issue_token(login_key, key)
    return jsonify({"ok": True, "login": login, "tg_id": login_key, "token": token})


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
    mine = [t for t in tasks if (t.get("owner") or "default") == owner]
    for t in mine:
        t["history"] = history_prices(owner, t["sku"])
    return jsonify(mine)


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
        if task.get("current_sbp"):
            append_history(owner, sku, task["current_sbp"])
            touch_last_check()
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
            append_history(owner, task["sku"], sbp)
            updated += 1
        if updated:
            save_json(DATA_FILE, tasks)
            touch_last_check()
    return jsonify({"ok": True, "updated": updated})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)

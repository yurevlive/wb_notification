"""Мониторинг цен WB + приём команд Telegram.

Запускается по расписанию в GitHub Actions, потому что на бесплатном
PythonAnywhere нет ни always-on, ни cron, а домены wbbasket.ru не входят
в белый список внешних сайтов.

Что делает за один запуск:
  1. забирает задачи с сервера (GET /tasks);
  2. проверяет цену каждого товара на CDN WB;
  3. шлёт уведомление в Telegram, если цена дошла до цели;
  4. разбирает накопившиеся команды бота (getUpdates);
  5. сохраняет состояние в state.json (коммитится workflow).

Сервер используется только как хранилище задач: сам он к WB обратиться
не может, поэтому цены здесь никуда не записываются (PUSH_PRICES=1, чтобы
включить, когда сервер научится принимать их от клиента).
"""

import json
import os
import sys
import time

import requests

from wb_common import fetch_product, parse_add_command, product_url

API_BASE = os.environ.get("WB_API_BASE", "").strip().rstrip("/") or "https://yurevlive.pythonanywhere.com"
TG_TOKEN = os.environ.get("TG_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
STATE_FILE = os.environ.get("STATE_FILE", "state.json")
DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
PUSH_PRICES = os.environ.get("PUSH_PRICES", "").lower() in ("1", "true", "yes")
TG_POLL_TIMEOUT = int(os.environ.get("TG_POLL_TIMEOUT", "8"))

HELP = (
    "🤖 WB.Track [by.Жекич]\n"
    "Отправьте: АРТИКУЛ ЦЕНА [ЛИМИТ]\n"
    "Пример: 596432419 420\n\n"
    "/list — задачи\n/del АРТИКУЛ — удалить"
)


def log(msg):
    print(msg, flush=True)


try:  # консоль Windows любит cp866/cp1251 и падает на ₽
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


# ---------------------------------------------------------------- состояние

def load_state():
    state = {"offset": 0, "bought": {}, "alerted": {}}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state.update(json.load(f))
        except (OSError, ValueError) as e:
            log("Не смог прочитать %s: %s" % (STATE_FILE, e))
    return state


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


# -------------------------------------------------------------------- telegram

def tg_url(method):
    return "https://api.telegram.org/bot%s/%s" % (TG_TOKEN, method)


def send_tg(chat_id, text):
    if DRY_RUN:
        log("[dry-run] TG -> %s: %s" % (chat_id, text.replace("\n", " | ")[:120]))
        return True
    if not TG_TOKEN:
        log("TG_TOKEN не задан, уведомление пропущено")
        return False
    try:
        r = requests.post(tg_url("sendMessage"), json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=15)
        return r.status_code == 200
    except requests.RequestException as e:
        log("Ошибка отправки в TG: %s" % e)
        return False


def api_register_contact(username, tg_id, name=""):
    """Говорит серверу, что @username = этот id, чтобы вход работал по логину."""
    if DRY_RUN:
        return True
    headers = {}
    token = os.environ.get("WORKER_TOKEN", "").strip()
    if token:
        headers["X-Worker-Token"] = token
    try:
        r = requests.post(API_BASE + "/tg_contact", json={"username": username, "id": str(tg_id), "name": name}, headers=headers, timeout=20)
        return r.status_code == 200
    except requests.RequestException as e:
        log("POST /tg_contact: %s" % e)
        return False


def api_start_login(nonce, tg_id, username="", name=""):
    """Сообщает серверу, что человек нажал Start по deep-link (вход без кода)."""
    if DRY_RUN:
        return True
    headers = {}
    token = os.environ.get("WORKER_TOKEN", "").strip()
    if token:
        headers["X-Worker-Token"] = token
    try:
        r = requests.post(API_BASE + "/tg_start", json={"nonce": nonce, "id": str(tg_id), "username": username, "name": name}, headers=headers, timeout=20)
        return r.status_code == 200
    except requests.RequestException as e:
        log("POST /tg_start: %s" % e)
        return False


def poll_telegram(state):
    if not TG_TOKEN:
        log("TG_TOKEN не задан — команды бота не разбираются")
        return False
    offset = int(state.get("offset") or 0)
    changed = False
    try:
        r = requests.get(tg_url("getUpdates"), params={"offset": offset, "timeout": TG_POLL_TIMEOUT}, timeout=TG_POLL_TIMEOUT + 15)
        if r.status_code == 409:
            log("webhook включён — команды бота обрабатывает сервер")
            return False
        if r.status_code != 200:
            log("getUpdates: HTTP %s" % r.status_code)
            return False
        updates = r.json().get("result", [])
    except (requests.RequestException, ValueError) as e:
        log("Ошибка опроса TG: %s" % e)
        return False

    for upd in updates:
        state["offset"] = upd["update_id"] + 1
        changed = True
        msg = upd.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat = msg.get("chat") or {}
        if not chat.get("id"):
            continue
        if chat.get("type") == "private" and chat.get("username"):
            api_register_contact(chat["username"], chat["id"], chat.get("first_name") or "")
        if not text:
            continue
        parts = text.split()
        if len(parts) >= 2 and parts[0].lower().split("@")[0] == "/start":
            api_start_login(parts[1], chat["id"], chat.get("username") or "", chat.get("first_name") or "")
        try:
            handle_command(str(chat["id"]), text, state)
        except Exception as e:  # одна плохая команда не должна валить запуск
            log("Ошибка обработки команды %r: %s" % (text, e))
    return changed


# ----------------------------------------------------------------------- api

def api_tasks():
    headers = {}
    token = os.environ.get("WORKER_TOKEN", "").strip()
    if token:
        headers["X-Worker-Token"] = token
    try:
        r = requests.get(API_BASE + "/tasks", params={"all": "1"}, headers=headers, timeout=20)
        if r.status_code != 200:
            log("GET /tasks: HTTP %s" % r.status_code)
            return []
        data = r.json()
        return data if isinstance(data, list) else []
    except (requests.RequestException, ValueError) as e:
        log("Не смог получить задачи: %s" % e)
        return []


def api_post_task(payload):
    if DRY_RUN:
        log("[dry-run] POST /tasks %s" % json.dumps(payload, ensure_ascii=False)[:160])
        return True
    try:
        r = requests.post(API_BASE + "/tasks", json=payload, timeout=20)
        return r.status_code == 200
    except requests.RequestException as e:
        log("POST /tasks: %s" % e)
        return False


def api_delete_task(sku, owner=""):
    if DRY_RUN:
        log("[dry-run] DELETE /tasks/%s" % sku)
        return True
    try:
        r = requests.delete(API_BASE + "/tasks/%s" % sku, params={"user": owner}, timeout=20)
        return r.status_code == 200
    except requests.RequestException as e:
        log("DELETE /tasks: %s" % e)
        return False


# ------------------------------------------------------------------- команды

def handle_command(chat_id, text, state):
    if TG_CHAT_ID and str(chat_id) != TG_CHAT_ID:
        send_tg(chat_id, "⛔ Доступ закрыт.")
        return

    if text.startswith(("/start", "/help")):
        send_tg(chat_id, HELP)
        return

    if text.startswith("/list"):
        tasks = api_tasks()
        if not tasks:
            send_tg(chat_id, "📭 Список пуст.")
            return
        lines = ["📋 Текущие задачи:\n"]
        for t in tasks:
            sku = int(t["sku"])
            bought = max(int(t.get("bought") or 0), int(state["bought"].get(str(sku), 0)))
            mark = "✅" if bought >= int(t.get("limit") or 1) else "⏳"
            cur = "%s ₽" % t["current_sbp"] if t.get("current_sbp") else "—"
            lines.append(
                "%s %s (Арт: %s)\nСейчас: %s | Цель: до %s ₽ (%d/%d)"
                % (mark, t.get("name") or sku, sku, cur, t["target_price"], bought, int(t.get("limit") or 1))
            )
        send_tg(chat_id, "\n\n".join(lines))
        return

    if text.startswith("/del"):
        parts = text.split()
        sku = None
        if len(parts) >= 2:
            try:
                sku = int(parts[1])
            except ValueError:
                sku = None
        if sku is None:
            send_tg(chat_id, "⚠️ Формат: /del АРТИКУЛ")
            return
        ok = api_delete_task(sku)
        send_tg(chat_id, "🗑 Артикул %d удалён." % sku if ok else "⚠️ Артикул %d не найден." % sku)
        return

    parsed = parse_add_command(text)
    if not parsed:
        send_tg(chat_id, "⚠️ Формат: АРТИКУЛ ЦЕНА (например: 596432419 420)")
        return

    sku, target, limit = parsed
    send_tg(chat_id, "⏳ Загружаю товар...")
    name, wallet, sbp, image = fetch_product(sku)
    payload = {
        "owner": "telegram",
        "sku": sku,
        "target_price": target,
        "limit": limit,
        "name": name,
        "image": image,
        "current_sbp": sbp,
        "current_wallet": wallet,
    }
    ok = api_post_task(payload)
    if not ok:
        send_tg(chat_id, "⚠️ Не смог сохранить задачу: сервер недоступен.")
        return
    cur = "%s ₽" % sbp if sbp else "—"
    send_tg(
        chat_id,
        "✅ Добавлено!\n\n📦 %s\n🔢 Арт: %d\n💳 Сейчас (СБП): %s\n🎯 Цель: до %d ₽ (%d шт.)"
        % (name, sku, cur, target, limit),
    )


# ------------------------------------------------------------------ мониторинг

def check_prices(state):
    tasks = api_tasks()
    if not tasks:
        log("Задач нет — проверять нечего")
        return False

    changed = False
    for t in tasks:
        try:
            sku = int(t["sku"])
            target = int(t["target_price"])
        except (KeyError, TypeError, ValueError):
            log("Пропускаю битую задачу: %r" % (t,))
            continue

        limit = int(t.get("limit") or 1)
        bought = max(int(t.get("bought") or 0), int(state["bought"].get(str(sku), 0)))
        name, wallet, sbp, image = fetch_product(sku)
        log("[%d] %s: СБП %s ₽ | Кошелёк %s ₽ (цель <= %d ₽, %d/%d)"
            % (sku, name, sbp, wallet, target, bought, limit))

        if sbp is None:
            continue

        if PUSH_PRICES:
            api_post_task({
                "owner": t.get("owner") or "",
                "sku": sku,
                "target_price": target,
                "limit": limit,
                "name": name,
                "image": image,
                "current_sbp": sbp,
                "current_wallet": wallet,
            })

        if bought >= limit:
            continue
        if sbp > target:
            if state["alerted"].get(str(sku)) is not None:
                state["alerted"].pop(str(sku), None)
                changed = True
            continue
        if state["alerted"].get(str(sku)) == sbp:
            continue

        sent = send_tg(TG_CHAT_ID or t.get("owner") or "", (
            "🔔 Цена WB дошла до цели!\n"
            "%s (Арт: %d)\n"
            "💳 СБП: %s ₽ | 👛 Кошелёк: %s ₽\n"
            "🎯 Цель: до %d ₽ (%d/%d)\n"
            "🔗 %s"
        ) % (name, sku, sbp, wallet, target, bought + 1, limit, product_url(sku)))
        if not sent:
            continue
        state["bought"][str(sku)] = bought + 1
        state["alerted"][str(sku)] = sbp
        changed = True
        time.sleep(1)

    return changed


def main():
    state = load_state()
    changed = poll_telegram(state)
    changed = check_prices(state) or changed
    if changed:
        save_state(state)
    else:
        log("Состояние не изменилось")
    return 0


if __name__ == "__main__":
    sys.exit(main())

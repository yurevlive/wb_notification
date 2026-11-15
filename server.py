import json
import os
import random
import subprocess
import threading
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)
DATA_FILE = "tasks.json"
TG_TOKEN = "9103986883:AAH1tV5Pn9Ti4cUGzAeLVdGFMbcWrWeDW84"
TG_CHAT_ID = "7488893558"
COEF_WALLET = 426 / 395
COEF_SBP = 454 / 395

wake_event = threading.Event()
file_lock = threading.Lock()

def tg_url(method):
    return "".join(["ht", "tps://", "api.", "telegram.org", "/b", "ot", TG_TOKEN, "/", method])

def wb_cdn_base(host, vol, part, sku):
    return "".join(["ht", "tps://", f"basket-{host}.", "wbbasket.ru", f"/vol{vol}/part{part}/{sku}"])

def wb_item_url(sku):
    return "".join(["ht", "tps://", "www.", "wildberries.ru", f"/catalog/{sku}/detail.aspx"])

def load_tasks():
    with file_lock:
        if not os.path.exists(DATA_FILE):
            return []
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

def save_tasks(tasks):
    with file_lock:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=2)

def get_basket_host(vol):
    limits = (143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601, 1655, 1919, 2045, 2189, 2405, 2621, 2837, 3053, 3269, 3485, 3701, 3917, 4133, 4349, 4565, 4877, 5189, 5501, 5813, 6125, 6437, 6749, 7061, 7373, 7685)
    for i, lim in enumerate(limits, 1):
        if vol <= lim:
            return f"{i:02d}"
    return "36"

def get_wb_product(sku):
    vol, part = sku // 100000, sku // 1000
    host = get_basket_host(vol)
    base_path = wb_cdn_base(host, vol, part, sku)
    image_url = f"{base_path}/images/c246x328/1.webp"
    headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}
    try:
        r_card = requests.get(f"{base_path}/info/ru/card.json", headers=headers, timeout=10)
        name = r_card.json().get("imt_name", f"Товар {sku}") if r_card.status_code == 200 else f"Товар {sku}"
        r_price = requests.get(f"{base_path}/info/price-history.json", headers=headers, timeout=10)
        if r_price.status_code == 200 and r_price.json():
            base_rub = r_price.json()[-1].get("price", {}).get("RUB", 0) // 100
            if base_rub > 0:
                return name, round(base_rub * COEF_WALLET), round(base_rub * COEF_SBP), image_url
    except Exception as e:
        print(f"Ошибка данных {sku}: {e}")
    return f"Товар {sku}", None, None, image_url

def create_or_update_task(sku, target_price, limit=1):
    name, price_wallet, price_sbp, image_url = get_wb_product(sku)
    item = {"sku": sku, "target_price": target_price, "limit": limit, "bought": 0, "name": name, "image": image_url, "current_sbp": price_sbp, "current_wallet": price_wallet}
    tasks = [t for t in load_tasks() if t["sku"] != sku]
    tasks.append(item)
    save_tasks(tasks)
    wake_event.set()
    return item

def remove_task(sku):
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t["sku"] != sku]
    save_tasks(new_tasks)
    return len(tasks) != len(new_tasks)

@app.route("/tasks", methods=["GET"])
def get_tasks():
    return jsonify(load_tasks())

@app.route("/tasks", methods=["POST"])
def add_task():
    d = request.json
    create_or_update_task(int(d["sku"]), int(d["target_price"]), int(d.get("limit", 1)))
    return jsonify({"status": "ok"})

@app.route("/tasks/<int:sku>", methods=["DELETE"])
def delete_task(sku):
    remove_task(sku)
    return jsonify({"status": "deleted"})

def send_tg(chat_id, text):
    try:
        requests.post(tg_url("sendMessage"), json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"Ошибка TG: {e}")

def open_in_yandex(sku):
    subprocess.run(["am", "start", "-a", "android.intent.action.VIEW", "-d", wb_item_url(sku), "-p", "com.yandex.browser"], check=False)

def handle_tg_text(chat_id, text):
    if text.startswith(("/start", "/help")):
        send_tg(chat_id, "🤖 WB.Track [by.Жекич]\nОтправьте: АРТИКУЛ ЦЕНА [ЛИМИТ]\nПример: 596432419 420\n\n/list — задачи\n/del АРТИКУЛ — удалить")
        return
    if text.startswith("/list"):
        tasks = load_tasks()
        if not tasks:
            send_tg(chat_id, "📭 Список пуст.")
            return
        lines = ["📋 Текущие задачи:\n"]
        for t in tasks:
            st = "✅" if t["bought"] >= t["limit"] else "⏳"
            cur = f"{t.get('current_sbp')} ₽" if t.get("current_sbp") else "—"
            lines.append(f"{st} {t.get('name', t['sku'])} (Арт: {t['sku']})\nСейчас: {cur} | Цель: до {t['target_price']} ₽ ({t['bought']}/{t['limit']})")
        send_tg(chat_id, "\n\n".join(lines))
        return
    if text.startswith("/del"):
        parts = text.split()
        if len(parts) >= 2 and parts.isdigit():
            ok = remove_task(int(parts))
            send_tg(chat_id, f"🗑 Артикул {parts} удален." if ok else f"⚠️ Артикул {parts} не найден.")
        return

    parts = text.replace(",", " ").split()
    if len(parts) >= 2 and parts.isdigit() and parts.isdigit():
        sku, target = int(parts), int(parts)
        limit = int(parts) if (len(parts) >= 3 and parts.isdigit()) else 1
        send_tg(chat_id, "⏳ Загружаю товар...")
        item = create_or_update_task(sku, target, limit)
        cur = f"{item['current_sbp']} ₽" if item["current_sbp"] else "—"
        send_tg(chat_id, f"✅ Добавлено и синхронизировано!\n\n📦 {item['name']}\n🔢 Арт: {sku}\n💳 Сейчас (СБП): {cur}\n🎯 Цель: до {target} ₽ ({limit} шт.)")
    else:
        send_tg(chat_id, "⚠️ Формат: АРТИКУЛ ЦЕНА (например: 596432419 420)")

def telegram_listener():
    print("Прием команд из Telegram запущен...")
    offset = 0
    while True:
        try:
            r = requests.get(tg_url("getUpdates"), params={"offset": offset, "timeout": 25}, timeout=30)
            if r.status_code == 200:
                for upd in r.json().get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message", {})
                    if msg.get("text") and msg.get("chat"):
                        handle_tg_text(str(msg["chat"]["id"]), msg["text"].strip())
        except Exception as e:
            print(f"Ошибка опроса TG: {e}")
            time.sleep(5)

def worker():
    print("Фоновый мониторинг WB запущен...")
    while True:
        wake_event.clear()
        tasks = load_tasks()
        changed = False
        for t in tasks:
            name, w_price, s_price, img = get_wb_product(t["sku"])
            if name and t.get("name") != name:
                t["name"], changed = name, True
            if img and t.get("image") != img:
                t["image"], changed = img, True
            if s_price is not None:
                if t.get("current_sbp") != s_price or t.get("current_wallet") != w_price:
                    t["current_sbp"], t["current_wallet"], changed = s_price, w_price, True
                print(f"Проверка [{t['sku']}] {name}: СБП {s_price} ₽ | Кошелек {w_price} ₽ (цель <= {t['target_price']} ₽)")
                if t["bought"] < t["limit"] and s_price <= t["target_price"]:
                    send_tg(TG_CHAT_ID, f"🔔 Цена WB упала!\n{name} (Арт: {t['sku']})\n💳 СБП: {s_price} ₽ | 👛 Кошелек: {w_price} ₽\nОткрываю Яндекс.Браузер...")
                    open_in_yandex(t["sku"])
                    t["bought"] += 1
                    changed = True
        if changed:
            save_tasks(tasks)
        wake_event.wait(random.randint(45, 75))

if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=telegram_listener, daemon=True).start()
    app.run(host="127.0.0.1", port=8000)

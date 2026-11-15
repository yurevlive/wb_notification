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
    if vol <= 143: return "01"
    if vol <= 287: return "02"
    if vol <= 431: return "03"
    if vol <= 719: return "04"
    if vol <= 1007: return "05"
    if vol <= 1061: return "06"
    if vol <= 1115: return "07"
    if vol <= 1169: return "08"
    if vol <= 1313: return "09"
    if vol <= 1601: return "10"
    if vol <= 1655: return "11"
    if vol <= 1919: return "12"
    if vol <= 2045: return "13"
    if vol <= 2189: return "14"
    if vol <= 2405: return "15"
    if vol <= 2621: return "16"
    if vol <= 2837: return "17"
    if vol <= 3053: return "18"
    if vol <= 3269: return "19"
    if vol <= 3485: return "20"
    if vol <= 3701: return "21"
    if vol <= 3917: return "22"
    if vol <= 4133: return "23"
    if vol <= 4349: return "24"
    if vol <= 4565: return "25"
    if vol <= 4877: return "26"
    if vol <= 5189: return "27"
    if vol <= 5501: return "28"
    if vol <= 5813: return "29"
    if vol <= 6125: return "30"
    if vol <= 6437: return "31"
    if vol <= 6749: return "32"
    if vol <= 7061: return "33"
    if vol <= 7373: return "34"
    if vol <= 7685: return "35"
    return "36"

def get_wb_product(sku):
    vol = sku // 100000
    part = sku // 1000
    host = get_basket_host(vol)
    p1 = "https" + "://"
    cdn_host = f"basket-{host}.wbbasket.ru"
    base_path = f"{p1}{cdn_host}/vol{vol}/part{part}/{sku}"
    url = f"{base_path}/info/price-history.json"
    card_url = f"{base_path}/info/ru/card.json"
    image_url = f"{base_path}/images/c246x328/1.webp"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    }
    try:
        r_card = requests.get(card_url, headers=headers, timeout=10)
        name = r_card.json().get("imt_name", f"Товар {sku}") if r_card.status_code == 200 else f"Товар {sku}"

        r_price = requests.get(url, headers=headers, timeout=10)
        if r_price.status_code == 200:
            history = r_price.json()
            if history:
                last_entry = history[-1]
                base_rub = last_entry.get("price", {}).get("RUB", 0) // 100
                if base_rub > 0:
                    price_wallet = round(base_rub * COEF_WALLET)
                    price_sbp = round(base_rub * COEF_SBP)
                    return name, price_wallet, price_sbp, image_url
    except Exception as e:
        print(f"Ошибка получения данных для {sku}: {e}")
    return f"Товар {sku}", None, None, image_url

def create_or_update_task(sku, target_price, limit=1):
    name, price_wallet, price_sbp, image_url = get_wb_product(sku)
    item = {
        "sku": sku,
        "target_price": target_price,
        "limit": limit,
        "bought": 0,
        "name": name,
        "image": image_url,
        "current_sbp": price_sbp,
        "current_wallet": price_wallet
    }
    current_tasks = load_tasks()
    current_tasks = [t for t in current_tasks if t["sku"] != sku]
    current_tasks.append(item)
    save_tasks(current_tasks)
    wake_event.set()
    return item

def remove_task(sku):
    current_tasks = load_tasks()
    new_tasks = [t for t in current_tasks if t["sku"] != sku]
    save_tasks(new_tasks)
    return len(current_tasks) != len(new_tasks)

@app.route("/tasks", methods=["GET"])
def get_tasks():
    return jsonify(load_tasks())

@app.route("/tasks", methods=["POST"])
def add_task():
    data = request.json
    create_or_update_task(int(data["sku"]), int(data["target_price"]), int(data.get("limit", 1)))
    return jsonify({"status": "ok"})

@app.route("/tasks/<int:sku>", methods=["DELETE"])
def delete_task(sku):
    remove_task(sku)
    return jsonify({"status": "deleted"})

def tg_api_url(method):
    p1 = "https" + "://"
    p2 = "api." + "telegram.org"
    return f"{p1}{p2}/bot{TG_TOKEN}/{method}"

def send_tg_message(chat_id, text):
    try:
        requests.post(tg_api_url("sendMessage"), json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"Ошибка Telegram: {e}")

def send_alerts(title, text):
    print(f"[УВЕДОМЛЕНИЕ] {title}: {text}")
    send_tg_message(TG_CHAT_ID, f"🔔 {title}\n{text}")

def open_in_yandex(sku):
    p1 = "https" + "://"
    wb_url = f"{p1}www.wildberries.ru/catalog/{sku}/detail.aspx"
    try:
        subprocess.run([
            "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", wb_url,
            "-p", "com.yandex.browser"
        ], check=False)
    except Exception as e:
        print(f"Не удалось открыть Яндекс.Браузер: {e}")

def telegram_listener():
    print("Прием команд из Telegram запущен...")
    offset = 0
    while True:
        try:
            r = requests.get(tg_api_url("getUpdates"), params={"offset": offset, "timeout": 25}, timeout=30)
            if r.status_code == 200:
                updates = r.json().get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1
                    msg = upd.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    text = msg.get("text", "").strip()
                    if not text or not chat_id:
                        continue

                    if text.startswith("/start") or text.startswith("/help"):
                        send_tg_message(chat_id, "🤖 WB.Track [by.Жекич]\nОтправьте: АРТИКУЛ ЦЕНА [ЛИМИТ]\nПример: 596432419 420\n\n/list — список задач\n/del АРТИКУЛ — удалить")
                    elif text.startswith("/list"):
                        tasks = load_tasks()
                        if not tasks:
                            send_tg_message(chat_id, "📭 Список пуст.")
                        else:
                            lines = ["📋 Текущие задачи:\n"]
                            for t in tasks:
                                st = "✅" if t["bought"] >= t["limit"] else "⏳"
                                cur = f"{t.get('current_sbp')} ₽" if t.get("current_sbp") else "—"
                                lines.append(f"{st} {t.get('name', t['sku'])} (Арт: {t['sku']})\nСейчас: {cur} | Цель: до {t['target_price']} ₽ ({t['bought']}/{t['limit']})")
                            send_tg_message(chat_id, "\n\n".join(lines))
                    elif text.startswith("/del"):
                        parts = text.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            sku = int(parts[1])
                            if remove_task(sku):
                                send_tg_message(chat_id, f"🗑 Артикул {sku} удален.")
                            else:
                                send_tg_message(chat_id, f"⚠️ Артикул {sku} не найден.")
                    else:
                        parts = text.replace(",", " ").split()
                        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                            sku = int(parts[0])
                            target = int(parts[1])
                            limit = int(parts[2]) if (len(parts) >= 3 and parts[2].isdigit()) else 1
                            send_tg_message(chat_id, "⏳ Загружаю данные товара...")
                            item = create_or_update_task(sku, target, limit)
                            cur_sbp = f"{item['current_sbp']} ₽" if item["current_sbp"] else "—"
                            send_tg_message(chat_id, f"✅ Добавлено и синхронизировано!\n\n📦 {item['name']}\n🔢 Артикул: {sku}\n💳 Сейчас (СБП): {cur_sbp}\n🎯 Цель: до {target} ₽ ({limit} шт.)")
                        else:
                            send_tg_message(chat_id, "⚠️ Отправьте артикул и цену через пробел, например:\n596432419 420")
        except Exception as e:
            print(f"Ошибка Telegram: {e}")
            time.sleep(5)

def worker():
    print("Фоновый мониторинг WB запущен...")
    while True:
        wake_event.clear()
        current_tasks = load_tasks()
        changed = False
        for t in current_tasks:
            name, price_wallet, price_sbp, image_url = get_wb_product(t["sku"])
            if name and t.get("name") != name:
                t["name"] = name
                changed = True
            if image_url and t.get("image") != image_url:
                t["image"] = image_url
                changed = True

            if price_sbp is not None:
                if t.get("current_sbp") != price_sbp or t.get("current_wallet") != price_wallet:
                    t["current_sbp"] = price_sbp
                    t["current_wallet"] = price_wallet
                    changed = True

                print(f"Проверка [{t['sku']}] {name}: СБП {price_sbp} ₽ | Кошелек {price_wallet} ₽ (цель <= {t['target_price']} ₽)")
                if t["bought"] < t["limit"] and price_sbp <= t["target_price"]:
                    send_alerts("Цена WB упала!", f"{name} (Арт: {t['sku']})\n💳 СБП / при получении: {price_sbp} ₽\n👛 WB Кошелек: {price_wallet} ₽\nОткрываю товар в Яндекс.Браузере...")
                    open_in_yandex(t["sku"])
                    t["bought"] += 1
                    changed = True

        if changed:

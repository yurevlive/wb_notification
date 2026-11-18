import os
import time

import flet as ft
import requests

S = chr(47)
API = os.environ.get("WB_API") or "".join(["ht", "tps:", S, S, "yurevlive.", "pythonanywhere.", "com"])
WB = "".join(["ht", "tps:", S, S, "www.", "wildberries.", S, "ru", S, "catalog", S])
NET_TIMEOUT = 8

APP_VERSION = "1.0.11"
REL_URL = "https://api.github.com/repos/yurevlive/wb_notification/releases/latest"

BG = "#0D1020"
CARD = "#13FFFFFF"
CARD2 = "#1AFFFFFF"
BORDER = "#1FFFFFFF"
TEXT = "#F2F4FF"
MUTED = "#9AA3C4"
VIOLET = "#8B5CF6"
CYAN = "#22D3EE"
PRICE = "#7DE3FF"
OK = "#22C55E"
WARN = "#F59E0B"
DANGER = "#EF4444"


def vt(ver):
    parts = []
    for p in str(ver).lstrip("v").split("."):
        parts.append(int(p) if p.isdigit() else 0)
    return tuple(parts + [0] * (3 - len(parts)))[:3]


def bars_chart(points, width_bars=26, height=54, rounded=True):
    pts = [int(p) for p in (points or []) if p]
    if len(pts) < 2:
        return ft.Container(height=height, content=ft.Text("нет истории", size=11, color=MUTED))
    step = max(1, len(pts) // width_bars)
    sample = pts[::step][-width_bars:]
    lo, hi = min(sample), max(sample)
    rng = max(1, hi - lo)
    falling = sample[-1] <= sample[0]
    color = CYAN if falling else WARN
    bars = []
    for p in sample:
        h = 6 + int((p - lo) / rng * (height - 6))
        bars.append(ft.Container(width=4, height=h, bgcolor=color, border_radius=2 if rounded else 0,
                                 opacity=0.45 + 0.5 * (h / height)))
    return ft.Row(bars, spacing=3, height=height, vertical_alignment=ft.CrossAxisAlignment.END)


def trend_info(history, current):
    pts = [int(p) for p in (history or []) if p]
    if len(pts) < 2 or not current:
        return "", MUTED
    prev = pts[-2]
    if current < prev:
        return "↓", OK
    if current > prev:
        return "↑", DANGER
    return "→", MUTED


def is_min_30(history, current):
    pts = [int(p) for p in (history or []) if p]
    if len(pts) < 3 or not current:
        return False
    return current <= min(pts[-30:])


def ago_text(ts):
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return ""
    if ts <= 0:
        return ""
    diff = int(time.time()) - ts
    if diff < 60:
        return "только что"
    if diff < 3600:
        return "%d мин назад" % (diff // 60)
    if diff < 86400:
        return "%d ч назад" % (diff // 3600)
    return "%d дн назад" % (diff // 86400)


def wb_open(page, sku):
    platform = str(getattr(page, "platform", "") or "").lower()
    if "android" not in platform:
        page.launch_url(WB + str(sku) + S + "detail.aspx")
        return
    intent = ("intent://www.wildberries.ru/catalog/%s/detail.aspx#Intent;"
              "scheme=https;package=com.wildberries.ru;"
              "S.browser_fallback_url=https%%3A%%2F%%2Fwww.wildberries.ru%%2Fcatalog%%2F%s%%2Fdetail.aspx;end"
              % (sku, sku))
    try:
        page.launch_url(intent)
    except Exception:
        page.launch_url(WB + str(sku) + S + "detail.aspx")


import re as _re


def parse_clipboard(text):
    t = (text or "").strip()
    if not t:
        return None, None, None
    sku = None
    m = _re.search(r"wildberries\.ru/catalog/(\d+)", t)
    if m:
        sku = int(m.group(1))
    if sku is None:
        m = _re.search(r"ozon\.ru/product/[^/]*?(\d{6,})", t)
        if m:
            sku = int(m.group(1))
    if sku is None:
        nums = [int(x) for x in _re.findall(r"\d{6,}", t)]
        if nums:
            sku = nums[0]
    if sku is None:
        try:
            sku = int(t.split()[0])
        except (ValueError, IndexError):
            return None, None, None
    price = None
    limit = None
    if "wildberries.ru" not in t and "ozon.ru" not in t:
        nums = []
        for part in t.split():
            try:
                nums.append(int(part))
            except ValueError:
                pass
        if len(nums) >= 2:
            price = nums[1]
        if len(nums) >= 3:
            limit = nums[2]
    return sku, price, limit


def fetch_wb(sku):
    vol, part = sku // 100000, sku // 1000
    lims = (143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601, 1655, 1919, 2045, 2189, 2405,
            2621, 2837, 3053, 3269, 3485, 3701, 3917, 4133, 4349, 4565, 4877, 5189, 5501, 5813,
            6125, 6437, 6749, 7061, 7373, 7685)
    h = "36"
    for i, l in enumerate(lims, 1):
        if vol <= l:
            h = f"{i:02d}"
            break
    base = "".join(["ht", "tps:", S, S, f"basket-{h}.", "wbbasket.", "ru", S, f"vol{vol}", S,
                    f"part{part}", S, str(sku)])
    img = base + S + "images" + S + "c246x328" + S + "1.webp"
    name, w_pr, s_pr = f"Товар {sku}", None, None
    try:
        rc = requests.get(base + S + "info" + S + "ru" + S + "card.json", timeout=NET_TIMEOUT)
        if rc.status_code == 200:
            name = rc.json().get("imt_name") or name
    except (requests.RequestException, ValueError):
        pass
    try:
        rp = requests.get(base + S + "info" + S + "price-history.json", timeout=NET_TIMEOUT)
        if rp.status_code == 200 and rp.json():
            rub = rp.json()[-1].get("price", {}).get("RUB", 0) // 100
            if rub > 0:
                w_pr, s_pr = round(rub * 426 / 395), round(rub * 454 / 395)
    except (requests.RequestException, ValueError):
        pass
    return name, w_pr, s_pr, img


def aurora_bg():
    return [
        ft.Container(left=-120, top=-140, width=420, height=420, border_radius=210,
                     gradient=ft.RadialGradient(colors=["#558B5CF6", "#008B5CF6"])),
        ft.Container(right=-140, top=260, width=380, height=380, border_radius=190,
                     gradient=ft.RadialGradient(colors=["#4022D3EE", "#0022D3EE"])),
        ft.Container(left=-60, bottom=-120, width=320, height=320, border_radius=160,
                     gradient=ft.RadialGradient(colors=["#338B5CF6", "#008B5CF6"])),
    ]


def main(page: ft.Page):
    page.title = "WB.Track [by.Жекич]"
    page.padding = 0
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.locale_configuration = ft.LocaleConfiguration(
        supported_locales=[ft.Locale("ru", "RU")], current_locale=ft.Locale("ru", "RU"))

    st = {"tasks": [], "user": "", "token": "", "reg": False, "busy": False, "tab": 0,
          "apk": "", "alerted_shown": False, "last_clip": ""}

    def bg(fn, *args):
        page.run_thread(fn, *args)

    def snack(text, ok=True, duration=3500):
        page.overlay.append(ft.SnackBar(
            content=ft.Text(text, color="white", size=13, weight=ft.FontWeight.W_500),
            bgcolor="#1B5E20" if ok else "#7F1D1D", duration=duration, behavior=ft.SnackBarBehavior.FLOATING))
        page.update()

    def headers():
        return {"Authorization": "Bearer " + st["token"]} if st.get("token") else {}

    # ---------------------------------------------------------------- авторизация
    a_t = ft.Text("Вход в кабинет", size=22, weight=ft.FontWeight.BOLD, color=TEXT)
    u_in = ft.TextField(hint_text="Логин", border_radius=14, filled=True, bgcolor=CARD,
                        border_color=BORDER, color=TEXT, height=52)
    p_in = ft.TextField(hint_text="Пароль", password=True, can_reveal_password=True, border_radius=14,
                        filled=True, bgcolor=CARD, border_color=BORDER, color=TEXT, height=52)
    rem = ft.Checkbox(label="Запомнить меня", value=True, active_color=VIOLET, label_style=ft.TextStyle(color=MUTED, size=12))
    tg_in = ft.TextField(hint_text="Числовой Telegram ID", border_radius=14, filled=True, bgcolor=CARD,
                         border_color=BORDER, color=TEXT, visible=False, height=52)
    tg_id_in = ft.TextField(hint_text="Логин Telegram, например @yurev0", border_radius=14, filled=True,
                            bgcolor=CARD, border_color=BORDER, color=TEXT, height=52)
    code_in = ft.TextField(hint_text="Код из Telegram", keyboard_type=ft.KeyboardType.NUMBER, border_radius=14,
                           filled=True, bgcolor=CARD, border_color=BORDER, color=TEXT, visible=False, height=52)
    a_err = ft.Text("", size=12, color=DANGER)
    b_txt = ft.Text("Войти", color="white", weight=ft.FontWeight.BOLD)
    sw_txt = ft.Text("Нет аккаунта? Регистрация", size=12, color=PRICE)
    tg_btn_txt = ft.Text("Войти через Telegram (1 касание)", color="white", weight=ft.FontWeight.BOLD)
    tg_login_btn = ft.Container(bgcolor="#2A8B5CF6", border_radius=14, height=48, alignment=ft.alignment.center,
                                content=tg_btn_txt, ink=True)
    send_btn = ft.Container(bgcolor="#2A22D3EE", border_radius=14, height=44, alignment=ft.alignment.center,
                            content=ft.Text("Отправить код", color=PRICE, size=13, weight=ft.FontWeight.W_600), ink=True)
    verify_btn = ft.Container(bgcolor="#2A22D3EE", border_radius=14, height=44, alignment=ft.alignment.center,
                              content=ft.Text("Войти по коду", color=PRICE, size=13, weight=ft.FontWeight.W_600),
                              ink=True, visible=False)
    auth_btn = ft.Container(bgcolor=CYAN, border_radius=14, height=50, alignment=ft.alignment.center,
                            content=b_txt, ink=True)

    def enter(u, token=""):
        st["user"], st["token"] = u, token or ""
        auth_view.visible = False
        shell.visible = True
        page.navigation_bar.visible = True
        page.floating_action_button.visible = True
        show_tab(st["tab"])
        page.update()

    def logout(e=None):
        st["user"] = st["token"] = ""
        try:
            page.client_storage.remove("wb_u")
            page.client_storage.remove("wb_token")
        except Exception:
            pass
        shell.visible = False
        page.navigation_bar.visible = False
        page.floating_action_button.visible = False
        auth_view.visible = True
        page.update()

    def toggle_reg(e):
        st["reg"] = not st["reg"]
        a_t.value = "Регистрация" if st["reg"] else "Вход в кабинет"
        b_txt.value = "Создать аккаунт" if st["reg"] else "Войти"
        sw_txt.value = "Уже есть аккаунт? Войти" if st["reg"] else "Нет аккаунта? Регистрация"
        tg_in.visible = st["reg"]
        a_err.value = ""
        page.update()

    def do_auth(e):
        u, p = u_in.value.strip().lower(), p_in.value.strip()
        if not u or not p:
            a_err.value = "Введите логин и пароль"
            page.update()
            return
        a_err.value = ""
        b_txt.value = "Подождите..."
        page.update()
        bg(_auth_request, u, p)

    def _auth_request(u, p):
        err, login, token = "", None, ""
        try:
            r = requests.post(API + S + ("register" if st["reg"] else "login"),
                              json={"login": u, "password": p, "tg_id": tg_in.value.strip()},
                              timeout=NET_TIMEOUT)
            data = r.json()
            if data.get("ok"):
                login = data.get("login") or u
                token = data.get("token") or ""
                if rem.value:
                    page.client_storage.set("wb_u", login)
                    page.client_storage.set("wb_token", token)
            else:
                err = data.get("error", "Ошибка входа")
        except (requests.RequestException, ValueError):
            err = "Сервер недоступен"
        b_txt.value = "Создать аккаунт" if st["reg"] else "Войти"
        if login:
            enter(login, token)
            load()
        else:
            a_err.value = err
            page.update()

    def do_request_code(e):
        tid = tg_id_in.value.strip()
        if not tid:
            a_err.value = "Введите логин или ID Telegram"
            page.update()
            return
        a_err.value = ""
        page.update()
        bg(_request_code, tid)

    def _request_code(tid):
        try:
            data = requests.post(API + S + "request_code", json={"tg_id": tid}, timeout=NET_TIMEOUT).json()
        except (requests.RequestException, ValueError):
            data = {"ok": False, "error": "Сервер недоступен"}
        if data.get("ok"):
            code_in.visible = verify_btn.visible = True
            if data.get("sent") is False:
                a_err.value = data.get("error") or "Код не отправлен"
                a_err.color = DANGER
            else:
                a_err.value = "Код отправлен. Проверьте Telegram."
                a_err.color = OK
        else:
            a_err.value = data.get("error", "Ошибка")
            a_err.color = DANGER
        page.update()

    def do_verify(e):
        tid, code = tg_id_in.value.strip(), code_in.value.strip()
        if not tid or not code:
            a_err.value = "Введите логин и код"
            page.update()
            return
        bg(_verify, tid, code)

    def _verify(tid, code):
        login, token, err = None, None, ""
        try:
            data = requests.post(API + S + "verify_code", json={"tg_id": tid, "code": code}, timeout=NET_TIMEOUT).json()
            if data.get("ok"):
                login, token = data.get("login") or ("tg_" + tid), data.get("token") or ""
                if rem.value:
                    page.client_storage.set("wb_u", login)
                    page.client_storage.set("wb_token", token)
            else:
                err = data.get("error", "Неверный код")
        except (requests.RequestException, ValueError):
            err = "Сервер недоступен"
        if login:
            enter(login, token)
            load()
        else:
            a_err.value = err
            page.update()

    def do_tg_login(e):
        a_err.value, a_err.color = "", DANGER
        page.update()
        bg(_tg_login)

    def _tg_login():
        nonce, link, err = "", "", ""
        try:
            d = requests.post(API + S + "start_login", json={}, timeout=NET_TIMEOUT).json()
            if d.get("ok"):
                nonce, link = d.get("nonce") or "", d.get("url") or ""
            else:
                err = d.get("error") or "Ошибка"
        except (requests.RequestException, ValueError):
            err = "Сервер недоступен"
        if not nonce:
            a_err.value = err or "Не удалось начать вход"
            page.update()
            return
        try:
            page.launch_url(link)
        except Exception:
            pass
        a_err.value, a_err.color = "Нажмите Start в Telegram — вход произойдёт сам", OK
        page.update()
        for _ in range(75):
            time.sleep(2)
            try:
                d = requests.get(API + S + "poll_login", params={"nonce": nonce}, timeout=NET_TIMEOUT).json()
            except (requests.RequestException, ValueError):
                continue
            if d.get("ok") and d.get("token"):
                if rem.value:
                    page.client_storage.set("wb_u", d["login"])
                    page.client_storage.set("wb_token", d["token"])
                enter(d["login"], d["token"])
                load()
                return
        a_err.value, a_err.color = "Время ожидания истекло", DANGER
        page.update()

    auth_view = ft.Container(
        visible=True, expand=True, padding=ft.padding.symmetric(horizontal=22, vertical=18),        content=ft.Column([
            ft.Container(height=26),
            ft.Container(width=76, height=76, border_radius=22, alignment=ft.alignment.center,
                         gradient=ft.LinearGradient(colors=[VIOLET, CYAN]),
                         content=ft.Icon(ft.Icons.TRENDING_DOWN_ROUNDED, size=40, color="white")),
            ft.Text("WB.Track", size=26, weight=ft.FontWeight.BOLD, color=TEXT),
            ft.Text("трекер цен Wildberries", size=12, color=MUTED),
            ft.Container(height=14),
            a_t, u_in, p_in, tg_in, rem, a_err,
            auth_btn,
            ft.Container(height=6),
            sw_txt,
            ft.Divider(height=22, color=BORDER),
            ft.Text("Вход через Telegram", size=13, color=TEXT, weight=ft.FontWeight.W_600),
            tg_login_btn,
            ft.Text("Если не сработало — получите код:", size=11, color=MUTED),
            tg_id_in, send_btn, code_in, verify_btn,
            ft.TextButton(content=ft.Text("Открыть @wb_jekich_bot", size=11, color=PRICE),
                          url="https://t.me/wb_jekich_bot"),
            ft.Container(height=20),
        ], spacing=10, scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    auth_btn.on_click = do_auth
    sw_txt.on_click = toggle_reg
    tg_login_btn.on_click = do_tg_login
    send_btn.on_click = do_request_code
    verify_btn.on_click = do_verify

    # ------------------------------------------------------------------- экраны
    title_lbl = ft.Text("WB.Track", size=19, weight=ft.FontWeight.BOLD, color=TEXT)
    status_dot = ft.Container(width=7, height=7, border_radius=4, bgcolor=CYAN)
    status_lbl = ft.Text("онлайн", size=11, color=MUTED)
    spin = ft.ProgressRing(width=12, height=12, stroke_width=2, color=CYAN, visible=False)
    user_lbl = ft.Text("", size=11, color=MUTED)

    cards_col = ft.Column(spacing=10)
    empty_box = ft.Container(visible=False, padding=40, alignment=ft.alignment.center,
                             content=ft.Column([
                                 ft.Icon(ft.Icons.INBOX_ROUNDED, size=54, color="#3A3A48"),
                                 ft.Text("Пока пусто", size=15, weight=ft.FontWeight.BOLD, color=MUTED),
                                 ft.Text("Добавьте артикул и цену — начнём следить", size=11, color="#5A5A66"),
                             ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6))

    srch = ft.TextField(hint_text="Поиск по артикулу или названию", height=44, border_radius=14,
                        filled=True, bgcolor=CARD, border_color=BORDER, color=TEXT,
                        prefix_icon=ft.Icons.SEARCH_ROUNDED, content_padding=ft.padding.symmetric(horizontal=14))

    home_screen = ft.Column([srch, cards_col, empty_box], spacing=12, visible=True)
    history_col = ft.Column(spacing=10)
    history_screen = ft.Column([history_col], spacing=10, visible=False)

    settings_screen = ft.Column([], spacing=12, visible=False, scroll=ft.ScrollMode.AUTO)

    def apply_search(e=None):
        render_cards()
        page.update()

    srch.on_change = apply_search

    def render_cards():
        cards_col.controls.clear()
        q = (srch.value or "").lower()
        tasks = [t for t in st["tasks"] if q in str(t["sku"]) or q in (t.get("name") or "").lower()]
        empty_box.visible = not tasks
        for t in tasks:
            cards_col.controls.append(task_card(t))

    def progress_value(t):
        sbp, target = t.get("current_sbp"), t.get("target_price") or 0
        if not sbp or not target:
            return 0.0
        return max(0.02, min(1.0, target / sbp))

    def task_card(t):
        sbp, wal, tgt = t.get("current_sbp"), t.get("current_wallet"), t.get("target_price") or 0
        if t["bought"] >= t.get("limit", 1):
            status, status_color = "✅ выкуплено", OK
        elif sbp and sbp <= tgt:
            status, status_color = "🔥 цель достигнута", CYAN
        elif sbp:
            status, status_color = "ещё %d ₽" % (sbp - tgt), MUTED
        else:
            status, status_color = "цена не загружена", MUTED
        arrow, arrow_color = trend_info(t.get("history") or [], sbp)
        price_txt = ("%s ₽" % f"{sbp:,}".replace(",", " ")) if sbp else "—"
        return ft.Container(
            bgcolor=CARD, border=ft.border.all(1, BORDER), border_radius=20, padding=10,
            content=ft.Row([
                ft.Container(width=58, height=78, border_radius=12, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                             bgcolor=CARD2, alignment=ft.alignment.center,
                             content=(ft.Image(src=t.get("image"), fit=ft.ImageFit.COVER, width=58, height=78)
                                      if t.get("image") else
                                      ft.Icon(ft.Icons.IMAGE_OUTLINED, size=22, color="#3A3A48"))),
                ft.Column([
                    ft.Text(t.get("name") or str(t["sku"]), size=12.5, color=TEXT, max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text("арт. %s" % t["sku"], size=10, color=MUTED),
                    ft.Row([
                        ft.Text(price_txt, size=25, weight=ft.FontWeight.W_800, color=PRICE),
                        ft.Text(arrow, size=15, color=arrow_color),
                        ft.Text("мин.30д", size=9, color=OK, weight=ft.FontWeight.W_700,
                                visible=is_min_30(t.get("history") or [], sbp)),
                        ft.Text(("кош. %s ₽" % f"{wal:,}".replace(",", " ")) if wal else "", size=10, color=MUTED),
                    ], spacing=6),
                    ft.ProgressBar(value=progress_value(t), height=4, color=VIOLET, bgcolor="#1AFFFFFF",
                                   border_radius=4),
                    ft.Row([
                        ft.Text("цель ≤ %s ₽" % f"{tgt:,}".replace(",", " "), size=10, color=MUTED),
                        ft.Text("·", size=10, color=MUTED),
                        ft.Text(status, size=10, color=status_color),
                        ft.Text("· %d/%d" % (t["bought"], t.get("limit", 1)), size=10, color=MUTED),
                    ], spacing=4),
                ], spacing=3, expand=True),
                ft.Column([
                    ft.IconButton(icon=ft.Icons.OPEN_IN_NEW_ROUNDED, icon_size=17, icon_color=MUTED,
                                  tooltip="Открыть в WB", on_click=lambda e, s=t["sku"]: wb_open(page, s)),
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT, icon_size=18, icon_color=MUTED,
                        items=[
                            ft.PopupMenuItem(text="Редактировать", on_click=lambda e, x=t: edit_task(x)),
                            ft.PopupMenuItem(text="Отметить покупку", on_click=lambda e, x=t: buy_task(x)),
                            ft.PopupMenuItem(text="Удалить", on_click=lambda e, x=t: delete_task(x["sku"])),
                        ]),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.START, alignment=ft.MainAxisAlignment.START))

    def render_history():
        history_col.controls.clear()
        tasks = st["tasks"]
        active = [t for t in tasks if t["bought"] < t.get("limit", 1)]
        done = [t for t in tasks if t["bought"] >= t.get("limit", 1)]
        for title, items in (("Отслеживается", active), ("Выкуплено", done)):
            if not items:
                continue
            history_col.controls.append(ft.Text(title, size=12, color=MUTED, weight=ft.FontWeight.W_600))
            for t in items:
                hist = t.get("history") or []
                pts = [int(x) for x in hist if x]
                lo = min(pts) if pts else 0
                hi = max(pts) if pts else 0
                avg = sum(pts) // len(pts) if pts else 0
                history_col.controls.append(ft.Container(
                    bgcolor=CARD, border=ft.border.all(1, BORDER), border_radius=18, padding=12,
                    content=ft.Column([
                        ft.Text(t.get("name") or str(t["sku"]), size=12.5, color=TEXT, max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text("арт. %s" % t["sku"], size=10, color=MUTED),
                        bars_chart(pts),
                        ft.Row([
                            ft.Text("мин %s ₽" % f"{lo:,}".replace(",", " "), size=10, color=OK),
                            ft.Text("сред %s ₽" % f"{avg:,}".replace(",", " "), size=10, color=MUTED),
                            ft.Text("макс %s ₽" % f"{hi:,}".replace(",", " "), size=10, color=WARN),
                            ft.Container(expand=True),
                            ft.Text("цель %s ₽" % f"{(t.get('target_price') or 0):,}".replace(",", " "),
                                    size=10, color=PRICE),
                        ], spacing=10),
                    ], spacing=4)))
        if not history_col.controls:
            history_col.controls.append(ft.Text("Пока нечего показывать", size=12, color=MUTED))

    def build_settings():
        settings_screen.controls = [
            ft.Container(bgcolor=CARD, border=ft.border.all(1, BORDER), border_radius=20, padding=14,
                         content=ft.Column([
                             ft.Text("Аккаунт", size=11, color=MUTED, weight=ft.FontWeight.W_600),
                             ft.Text(st["user"] or "—", size=15, color=TEXT, weight=ft.FontWeight.W_700),
                             ft.Container(height=6),
                             ft.Container(bgcolor=CARD2, border_radius=12, height=44, alignment=ft.alignment.center,
                                          content=ft.Text("Сменить пароль", size=13, color=TEXT), ink=True,
                                          on_click=lambda e: change_password()),
                             ft.Container(bgcolor=CARD2, border_radius=12, height=44, alignment=ft.alignment.center,
                                          content=ft.Text("Выйти", size=13, color=DANGER, weight=ft.FontWeight.W_600),
                                          ink=True, on_click=logout),
                         ], spacing=8)),
            ft.Container(bgcolor=CARD, border=ft.border.all(1, BORDER), border_radius=20, padding=14,
                         content=ft.Column([
                             ft.Text("Приложение", size=11, color=MUTED, weight=ft.FontWeight.W_600),
                             ft.Row([
                                 ft.Container(bgcolor=CARD2, border_radius=12, height=44, width=200,
                                              alignment=ft.alignment.center,
                                              content=ft.Text("Проверить обновления", size=13, color=TEXT),
                                              ink=True, on_click=lambda e: bg(check_updates)),
                                 upd_spinner,
                             ], spacing=10),
                             upd_status,
                             ft.Container(bgcolor=CARD2, border_radius=12, height=44, alignment=ft.alignment.center,
                                          visible=False, ink=True,
                                          content=ft.Text("Скачать обновление", size=13, color=CYAN),
                                          on_click=lambda e: page.launch_url(st["apk"]) if st.get("apk") else None),
                             ft.Container(height=4),
                             ft.Text("Уведомления", size=11, color=MUTED, weight=ft.FontWeight.W_600),
                             ft.Text("Критичные цены приходят в Telegram. Звук и вибрация — в следующей версии.",
                                     size=11, color=MUTED),
                             ft.TextButton(content=ft.Text("Открыть бота", size=11, color=CYAN),
                                           url="https://t.me/wb_jekich_bot"),
                         ], spacing=8)),
            ft.Container(bgcolor=CARD, border=ft.border.all(1, BORDER), border_radius=20, padding=14,
                         content=ft.Column([
                             ft.Text("О приложении", size=11, color=MUTED, weight=ft.FontWeight.W_600),
                             ft.Text("WB.Track — трекер цен Wildberries", size=12, color=TEXT),
                             ft.Text("версия %s" % APP_VERSION, size=11, color=MUTED),
                             ft.Text("сделано для личного трекинга скидок", size=10, color="#5A5A66"),
                         ], spacing=4)),
        ]

    def show_tab(idx):
        st["tab"] = idx
        home_screen.visible = idx == 0
        history_screen.visible = idx == 1
        settings_screen.visible = idx == 2
        page.floating_action_button.visible = idx == 0
        if idx == 1:
            render_history()
        if idx == 2:
            build_settings()
        page.update()

    upd_status = ft.Text("", size=12, color=CYAN, weight=ft.FontWeight.W_600, opacity=0,
                         animate_opacity=ft.Animation(350, "easeOut"), animate_scale=ft.Animation(350, "easeOut"))
    upd_spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=CYAN, visible=False)

    # ------------------------------------------------------------------- данные
    def set_status(text, color=CYAN):
        status_lbl.value = text
        status_dot.bgcolor = color
        page.update()

    def load(force=False):
        if st["busy"]:
            return
        st["busy"] = True
        spin.visible = True
        page.update()
        bg(_load_request, force)

    def _load_request(force=False):
        try:
            r = requests.get(API + S + "tasks", params={"user": st["user"]}, headers=headers(), timeout=NET_TIMEOUT)
            if r.status_code == 401:
                logout()
                return
            if r.status_code != 200:
                set_status("офлайн", DANGER)
                return
            tasks = r.json()
            for t in tasks:
                if force or not t.get("current_sbp"):
                    n, w, s, img = fetch_wb(t["sku"])
                    if s:
                        t["name"], t["current_wallet"], t["current_sbp"], t["image"] = n, w, s, img
            st["tasks"] = tasks
            try:
                h = requests.get(API + S + "health", timeout=NET_TIMEOUT).json()
                ts = int(h.get("last_check") or 0)
                txt = ago_text(ts)
                if txt:
                    diff = time.time() - ts
                    set_status("проверено " + txt, OK if diff < 3600 else (WARN if diff < 21600 else DANGER))
            except (requests.RequestException, ValueError, TypeError):
                pass
            reached = [t for t in tasks if t.get("current_sbp") and t["current_sbp"] <= t["target_price"]
                       and (t.get("bought") or 0) < (t.get("limit") or 1)]
            if reached and not st.get("alerted_shown"):
                st["alerted_shown"] = True
                snack("🔥 Цена достигнута: %s" % (reached[0].get("name") or reached[0]["sku"]))
            render_cards()
            if st["tab"] == 1:
                render_history()
            try:
                page.client_storage.set("wb_cache", str(len(tasks)))
            except Exception:
                pass
        except (requests.RequestException, ValueError):
            set_status("офлайн", DANGER)
        finally:
            st["busy"] = False
            spin.visible = False
            page.update()

    def add_task(e=None):
        sku_f = ft.TextField(hint_text="Артикул WB", keyboard_type=ft.KeyboardType.NUMBER, border_radius=14,
                             filled=True, bgcolor=CARD2, border_color=BORDER, color=TEXT)
        pr_f = ft.TextField(hint_text="Цена до (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=14,
                            filled=True, bgcolor=CARD2, border_color=BORDER, color=TEXT)
        lim_f = ft.TextField(value="1", prefix_text="Шт: ", keyboard_type=ft.KeyboardType.NUMBER, width=110,
                             border_radius=14, filled=True, bgcolor=CARD2, border_color=BORDER, color=TEXT)
        hint = ft.Text("", size=11, color=MUTED)

        def paste(e=None):
            try:
                txt = page.get_clipboard()
            except Exception:
                txt = ""
            sku, price, limit = parse_clipboard(txt or "")
            if sku:
                sku_f.value = str(sku)
                if price:
                    pr_f.value = str(price)
                if limit:
                    lim_f.value = str(limit)
                hint.value = "вставлено из буфера"
            else:
                hint.value = "в буфере нет ссылки WB"
            page.update()

        def submit(e=None):
            sku, price, limit = parse_clipboard(sku_f.value)
            if not sku:
                hint.value = "не нашёл артикул"
                page.update()
                return
            try:
                tgt = int(pr_f.value.strip()) if pr_f.value.strip() else (price or 0)
                lim = int(lim_f.value.strip() or 1)
            except ValueError:
                hint.value = "цена и количество — числа"
                page.update()
                return
            if tgt <= 0:
                hint.value = "укажи цену"
                page.update()
                return
            dlg.open = False
            page.update()
            st["busy"] = True
            bg(_add_request, sku, tgt, lim)

        dlg = ft.AlertDialog(
            modal=True, bgcolor="#151933",
            title=ft.Text("Новый артикул", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
            content=ft.Column([sku_f, ft.Row([pr_f, lim_f], spacing=8), hint,
                               ft.TextButton(content=ft.Text("Вставить из буфера", size=11, color=CYAN),
                                             on_click=paste)], spacing=10, tight=True, width=300),
            actions=[ft.TextButton(content=ft.Text("Отмена", color=MUTED), on_click=lambda e: close(dlg)),
                     ft.ElevatedButton(content=ft.Text("Добавить", color="#0B0B0F"), bgcolor=CYAN,
                                       on_click=submit)])
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def close(dlg):
        dlg.open = False
        page.update()

    def _add_request(sku, tgt, lim):
        try:
            n, w, s, img = fetch_wb(sku)
            requests.post(API + S + "tasks", json={
                "owner": st["user"], "sku": sku, "target_price": tgt, "limit": lim,
                "name": n, "image": img, "current_sbp": s, "current_wallet": w,
            }, headers=headers(), timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    def edit_task(t):
        pr_f = ft.TextField(value=str(t["target_price"]), label="Цена до (₽)", border_radius=14,
                            filled=True, bgcolor=CARD2, border_color=BORDER, color=TEXT,
                            keyboard_type=ft.KeyboardType.NUMBER)
        lim_f = ft.TextField(value=str(t.get("limit") or 1), label="Кол-во", border_radius=14,
                             filled=True, bgcolor=CARD2, border_color=BORDER, color=TEXT,
                             keyboard_type=ft.KeyboardType.NUMBER)
        err = ft.Text("", size=11, color=DANGER)

        def save(e=None):
            try:
                tgt = int(pr_f.value.strip())
                lim = int(lim_f.value.strip() or 1)
            except ValueError:
                err.value = "числа"
                page.update()
                return
            if tgt <= 0 or lim < 1:
                err.value = "больше нуля"
                page.update()
                return
            dlg.open = False
            page.update()
            st["busy"] = True
            bg(_save_task, t, tgt, lim)

        dlg = ft.AlertDialog(
            modal=True, bgcolor="#151933",
            title=ft.Text("Артикул %s" % t["sku"], size=15, weight=ft.FontWeight.BOLD, color=TEXT),
            content=ft.Column([pr_f, lim_f, err], spacing=10, tight=True, width=300),
            actions=[ft.TextButton(content=ft.Text("Отмена", color=MUTED), on_click=lambda e: close(dlg)),
                     ft.ElevatedButton(content=ft.Text("Сохранить", color="#0B0B0F"), bgcolor=CYAN,
                                       on_click=save)])
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _save_task(t, tgt, lim):
        payload = {"owner": st["user"], "sku": t["sku"], "target_price": tgt, "limit": lim,
                   "name": t.get("name"), "image": t.get("image"),
                   "current_sbp": t.get("current_sbp"), "current_wallet": t.get("current_wallet"),
                   "bought": t.get("bought") or 0}
        try:
            requests.post(API + S + "tasks", json=payload, headers=headers(), timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    def buy_task(t):
        st["busy"] = True
        bg(_buy, t)

    def _buy(t):
        payload = {"owner": st["user"], "sku": t["sku"], "bought": int(t.get("bought") or 0) + 1,
                   "target_price": t["target_price"], "limit": t.get("limit") or 1,
                   "name": t.get("name"), "image": t.get("image"),
                   "current_sbp": t.get("current_sbp"), "current_wallet": t.get("current_wallet")}
        try:
            requests.post(API + S + "tasks", json=payload, headers=headers(), timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    def delete_task(sku):
        confirm_dlg = ft.AlertDialog(
            modal=True, bgcolor="#151933",
            title=ft.Text("Удалить артикул %s?" % sku, size=15, color=TEXT),
            actions=[
                ft.TextButton(content=ft.Text("Отмена", color=MUTED), on_click=lambda e: close(confirm_dlg)),
                ft.ElevatedButton(content=ft.Text("Удалить", color="white"), bgcolor=DANGER,
                                  on_click=lambda e: (close(confirm_dlg), bg(_delete, sku)))])
        page.overlay.append(confirm_dlg)
        confirm_dlg.open = True
        page.update()

    def _delete(sku):
        try:
            requests.delete(API + S + "tasks" + S + str(sku), params={"user": st["user"]},
                            headers=headers(), timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    def change_password():
        old_f = ft.TextField(label="Старый пароль", password=True, can_reveal_password=True, border_radius=14,
                             filled=True, bgcolor=CARD2, border_color=BORDER, color=TEXT)
        new_f = ft.TextField(label="Новый пароль", password=True, can_reveal_password=True, border_radius=14,
                             filled=True, bgcolor=CARD2, border_color=BORDER, color=TEXT)
        err = ft.Text("", size=11, color=DANGER)

        def save(e=None):
            try:
                data = requests.post(API + S + "change_password", json={
                    "user": st["user"], "old_password": old_f.value.strip(), "new_password": new_f.value.strip(),
                }, headers=headers(), timeout=NET_TIMEOUT).json()
            except (requests.RequestException, ValueError):
                err.value = "нет связи"
                page.update()
                return
            if not data.get("ok"):
                err.value = data.get("error", "ошибка")
                page.update()
                return
            if data.get("token"):
                st["token"] = data["token"]
                try:
                    page.client_storage.set("wb_token", data["token"])
                except Exception:
                    pass
            dlg.open = False
            page.update()
            snack("Пароль изменён")

        dlg = ft.AlertDialog(
            modal=True, bgcolor="#151933",
            title=ft.Text("Смена пароля", size=15, weight=ft.FontWeight.BOLD, color=TEXT),
            content=ft.Column([old_f, new_f, err], spacing=10, tight=True, width=300),
            actions=[ft.TextButton(content=ft.Text("Отмена", color=MUTED), on_click=lambda e: close(dlg)),
                     ft.ElevatedButton(content=ft.Text("Сохранить", color="#0B0B0F"), bgcolor=CYAN,
                                       on_click=save)])
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def check_updates():
        upd_spinner.visible = True
        upd_status.opacity = 0
        upd_status.value = "Проверяю..."
        page.update()
        try:
            r = requests.get(REL_URL, timeout=NET_TIMEOUT, headers={"Accept": "application/vnd.github+json"})
            if r.status_code != 200:
                upd_status.value = "Не удалось проверить"
            else:
                data = r.json()
                tag = (data.get("tag_name") or "").lstrip("v")
                if vt(tag) <= vt(APP_VERSION):
                    upd_status.value = "✓ У вас последняя версия (%s)" % APP_VERSION
                else:
                    apk = next((a.get("browser_download_url") for a in data.get("assets") or []
                                if (a.get("name") or "").endswith(".apk")), "")
                    st["apk"] = apk
                    upd_status.value = "Доступна версия %s" % tag
                    if apk:
                        page.launch_url(apk)
        except (requests.RequestException, ValueError, AttributeError):
            upd_status.value = "Нет связи с сервером"
        upd_spinner.visible = False
        upd_status.opacity = 1
        page.update()

    # ------------------------------------------------------------------- оболочка
    header = ft.Container(
        padding=ft.padding.only(left=18, right=12, top=14, bottom=8),
        content=ft.Row([
            ft.Column([title_lbl, ft.Row([status_dot, spin, status_lbl], spacing=5)], spacing=2, expand=True),
            ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color=MUTED, icon_size=20,
                          tooltip="Обновить", on_click=lambda e: load(True)),
        ]))

    content = ft.Column([home_screen, history_screen, settings_screen], expand=True, scroll=ft.ScrollMode.AUTO,
                        spacing=0)
    CAP = 520

    shell_inner = ft.Column([header, ft.Container(content=content, expand=True,
                                                  padding=ft.padding.symmetric(horizontal=16)),
                             ft.Container(height=8)], expand=True, spacing=0)
    shell = ft.Container(visible=False, expand=True, content=shell_inner)
    auth_wrap = auth_view

    nav = ft.NavigationBar(
        selected_index=0,
        bgcolor="#E60C0E1E",
        indicator_color="#4D8B5CF6",
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME_ROUNDED, label="Главная"),
            ft.NavigationBarDestination(icon=ft.Icons.SHOW_CHART_OUTLINED, selected_icon=ft.Icons.SHOW_CHART_ROUNDED, label="История"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS_ROUNDED, label="Настройки"),
        ],
        on_change=lambda e: show_tab(e.control.selected_index),
        visible=False)

    fab = ft.FloatingActionButton(
        visible=False, elevation=6, bgcolor="transparent",
        content=ft.Container(width=56, height=56, border_radius=28, alignment=ft.alignment.center,
                             gradient=ft.LinearGradient(colors=[VIOLET, CYAN]),
                             content=ft.Icon(ft.Icons.ADD_ROUNDED, color="white", size=28)),
        on_click=add_task)

    page.navigation_bar = nav
    page.floating_action_button = fab
    page.add(ft.Stack(
        expand=True,
        controls=[
            ft.Container(expand=True, bgcolor=BG),
            *aurora_bg(),
            ft.Container(expand=True, content=ft.Column([auth_wrap, shell], expand=True)),
        ]))

    page.on_resize = None

    bg(check_updates)
    preview_user = os.environ.get("WB_PREVIEW_USER", "").strip()
    if preview_user:
        enter(preview_user, os.environ.get("WB_PREVIEW_TOKEN", "").strip())
        load()
        return
    try:
        saved = page.client_storage.get("wb_u") or ""
        saved_token = page.client_storage.get("wb_token") or ""
    except Exception:
        saved, saved_token = "", ""
    if saved:
        enter(saved, saved_token)
        load()


if __name__ == "__main__":
    ft.app(target=main)

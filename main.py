import flet as ft
import requests
import time

S = chr(47)
API = "".join(["ht", "tps:", S, S, "yurevlive.", "pythonanywhere.", "com"])
WB = "".join(["ht", "tps:", S, S, "www.", "wildberries.", "ru", S, "catalog", S])

NET_TIMEOUT = 8

# Версия указывается здесь. Тег релиза (v1.0.1) обязан совпадать с ней —
# сборка упадёт, если не совпадает, иначе приложение зациклится на "Обновить".
APP_VERSION = "1.0.5"
REL_URL = "https://api.github.com/repos/yurevlive/wb_notification/releases/latest"


def vt(ver):
    """'1.0.10' -> (1, 0, 10) для правильного сравнения версий."""
    parts = []
    for p in str(ver).lstrip("v").split("."):
        parts.append(int(p) if p.isdigit() else 0)
    return tuple(parts + [0] * (3 - len(parts)))[:3]


def sparkline(points, width_bars=22, height=30):
    """Мини-график цены из точек: столбики без внешних зависимостей."""
    pts = [int(p) for p in (points or []) if p]
    if len(pts) < 2:
        return ft.Container(visible=False)
    step = max(1, len(pts) // width_bars)
    sample = pts[::step][-width_bars:]
    lo, hi = min(sample), max(sample)
    rng = max(1, hi - lo)
    color = "#00E676" if sample[-1] <= sample[0] else "#FFB300"
    bars = []
    for p in sample:
        h = 4 + int((p - lo) / rng * (height - 4))
        bars.append(ft.Container(width=4, height=h, bgcolor=color, border_radius=2, opacity=0.55 + 0.45 * (h / height)))
    return ft.Row(bars, spacing=3, height=height, vertical_alignment=ft.CrossAxisAlignment.END)


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
    # intent:// заставляет Android открыть именно приложение WB, если оно
    # установлено; при отсутствии приложения сработает browser_fallback_url.
    intent = ("intent://www.wildberries.ru/catalog/%s/detail.aspx#Intent;"
              "scheme=https;package=com.wildberries.ru;"
              "S.browser_fallback_url=https%%3A%%2F%%2Fwww.wildberries.ru%%2Fcatalog%%2F%s%%2Fdetail.aspx;end"
              % (sku, sku))
    try:
        page.launch_url(intent)
    except Exception:
        page.launch_url(WB + str(sku) + S + "detail.aspx")


def fetch_wb(sku):
    vol, part = sku // 100000, sku // 1000
    lims = (143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601, 1655, 1919, 2045, 2189, 2405, 2621, 2837, 3053, 3269, 3485, 3701, 3917, 4133, 4349, 4565, 4877, 5189, 5501, 5813, 6125, 6437, 6749, 7061, 7373, 7685)
    h = "36"
    for i, l in enumerate(lims, 1):
        if vol <= l:
            h = f"{i:02d}"
            break
    base = "".join(["ht", "tps:", S, S, f"basket-{h}.", "wbbasket.", "ru", S, f"vol{vol}", S, f"part{part}", S, str(sku)])
    img = base + S + "images" + S + "c246x328" + S + "1.webp"
    name, w_pr, s_pr = f"Товар {sku}", None, None
    try:
        rc = requests.get(base + S + "info" + S + "ru" + S + "card.json", timeout=NET_TIMEOUT)
        if rc.status_code == 200: name = rc.json().get("imt_name") or name
    except (requests.RequestException, ValueError):
        pass
    try:
        rp = requests.get(base + S + "info" + S + "price-history.json", timeout=NET_TIMEOUT)
        if rp.status_code == 200 and rp.json():
            rub = rp.json()[-1].get("price", {}).get("RUB", 0) // 100
            if rub > 0: w_pr, s_pr = round(rub * 426 / 395), round(rub * 454 / 395)
    except (requests.RequestException, ValueError):
        pass
    return name, w_pr, s_pr, img


def main(page: ft.Page):
    page.title = "WB.Track [by.Жекич]"
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.locale_configuration = ft.LocaleConfiguration(supported_locales=[ft.Locale("ru", "RU")], current_locale=ft.Locale("ru", "RU"))
    # тема из сохранённых настроек
    _theme = page.client_storage.get("wb_theme") or "dark"
    if _theme == "light":
        P1, P2, BG, CARD, CARD2, BORDER = "#CB11AB", "#E91E8C", "#F5F5F7", "#FFFFFF", "#FFFFFF", "#E5E5EA"
        OK, WARN, DANGER = "#00B85A", "#F59E0B", "#EF4444"
        page.theme_mode = ft.ThemeMode.LIGHT
    else:
        P1, P2, BG, CARD, CARD2, BORDER = "#D946EF", "#7C3AED", "#0B0B12", "#16161F", "#1E1E2A", "#2A2A38"
        OK, WARN, DANGER = "#22C55E", "#F59E0B", "#EF4444"
        page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.bgcolor = BG
    st = {"tasks": [], "user": "", "token": "", "reg": False, "tg_mode": False, "q": "", "busy": False, "alerted_shown": False}

    def bg(fn, *args):
        """Сеть — только в фоне, иначе UI замирает чёрным экраном."""
        page.run_thread(fn, *args)

    def busy(on, text="Загрузка..."):
        st["busy"] = on
        spin.visible = on
        if on:
            st_lbl.value = text
        else:
            dot.color, st_lbl.value = "#00E676", "Онлайн"
        page.update()

    # ---------- авторизация ----------
    a_t = ft.Text("Вход в кабинет", size=22, weight="bold")
    u_in = ft.TextField(hint_text="Логин", border_radius=12, filled=True, bgcolor=CARD)
    p_in = ft.TextField(hint_text="Пароль", password=True, can_reveal_password=True, border_radius=12, filled=True, bgcolor=CARD)
    tg_in = ft.TextField(hint_text="Числовой Telegram ID", border_radius=12, filled=True, bgcolor=CARD, visible=False)
    rem = ft.Checkbox(label="Запомнить меня", value=True, active_color=P1)
    # --- Telegram-вход ---
    tg_id_in = ft.TextField(hint_text="Логин Telegram, например @yurev0", border_radius=12, filled=True, bgcolor=CARD)
    code_in = ft.TextField(hint_text="Код из Telegram", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, visible=False)
    send_btn = ft.ElevatedButton(content=ft.Text("Отправить код", color="white", weight="bold"), bgcolor=P1, height=46)
    tg_btn_txt = ft.Text("Войти через Telegram (1 касание)", color="white", weight="bold")
    tg_login_btn = ft.ElevatedButton(content=tg_btn_txt, bgcolor=P1, height=50)
    verify_btn = ft.ElevatedButton(content=ft.Text("Войти по коду", color="white", weight="bold"), bgcolor=P1, height=46, visible=False)
    mode_txt = ft.Text("Обычный вход", size=13, color=P1)
    a_err = ft.Text("", size=13, color="#FF5252")
    b_txt = ft.Text("Войти", color="white", weight="bold")
    sw_txt = ft.Text("Нет аккаунта? Регистрация", size=13, color="#E040FB")

    def toggle(e):
        st["reg"] = not st["reg"]
        a_t.value = "Регистрация" if st["reg"] else "Вход в кабинет"
        b_txt.value = "Создать аккаунт" if st["reg"] else "Войти"
        sw_txt.value = "Уже есть аккаунт? Войти" if st["reg"] else "Нет аккаунта? Регистрация"
        tg_in.visible, a_err.value = st["reg"], ""
        page.update()

    def enter(u, token=""):
        st["user"] = u
        st["token"] = token or ""
        u_lbl.value = f"Кабинет: {u}"
        auth_view.visible, main_b.visible = False, True
        page.update()

    def auth_headers():
        return {"Authorization": "Bearer " + st["token"]} if st.get("token") else {}

    def auth(e):
        u, p = u_in.value.strip().lower(), p_in.value.strip()
        if not u or not p:
            a_err.value = "Введите логин и пароль"
            page.update()
            return
        a_err.value = ""
        b_txt.value = "Подождите..."
        auth_btn.disabled = True
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
                    if token:
                        page.client_storage.set("wb_token", token)
                else:
                    try:
                        page.client_storage.remove("wb_u")
                        page.client_storage.remove("wb_token")
                    except Exception:
                        pass
            else:
                err = data.get("error", "Ошибка входа")
        except (requests.RequestException, ValueError):
            err = "Сервер недоступен, попробуйте позже"
        auth_btn.disabled = False
        b_txt.value = "Создать аккаунт" if st["reg"] else "Войти"
        if login:
            enter(login, token)
            load()
        else:
            a_err.value = err
            page.update()

    def logout(e):
        st["user"] = ""
        st["token"] = ""
        try:
            page.client_storage.remove("wb_u")
            page.client_storage.remove("wb_token")
        except Exception:
            pass
        main_b.visible, auth_view.visible = False, True
        page.update()

    def request_code(e):
        tid = tg_id_in.value.strip()
        if not tid:
            a_err.value = "Введите логин или ID Telegram"
            page.update()
            return
        a_err.value = ""
        send_btn.disabled = True
        send_btn.content = ft.Text("Отправляю...", color="white", weight="bold")
        page.update()
        bg(_request_code, tid)

    def _request_code(tid):
        err = ""
        try:
            r = requests.post(API + S + "request_code", json={"tg_id": tid}, timeout=NET_TIMEOUT)
            data = r.json()
            if data.get("ok"):
                code_in.visible = True
                verify_btn.visible = True
                send_btn.content = ft.Text("Отправить код повторно", color="white", weight="bold")
                if data.get("sent") is False:
                    a_err.value = data.get("error") or ("Код не отправлен: " + (data.get("send_error") or "ошибка"))
                    a_err.color = DANGER
                else:
                    a_err.value = "Код отправлен. Проверьте Telegram."
                    a_err.color = OK
            else:
                err = data.get("error", "Ошибка")
        except (requests.RequestException, ValueError):
            err = "Сервер недоступен"
        send_btn.disabled = False
        if err:
            a_err.value = err
        page.update()

    def verify_code(e):
        tid = tg_id_in.value.strip()
        code = code_in.value.strip()
        if not tid or not code:
            a_err.value = "Введите ID и код"
            page.update()
            return
        a_err.value = ""
        verify_btn.disabled = True
        verify_btn.content = ft.Text("Проверяю...", color="white", weight="bold")
        page.update()
        bg(_verify_code, tid, code)

    def _verify_code(tid, code):
        login, token, err = None, None, ""
        try:
            r = requests.post(API + S + "verify_code", json={"tg_id": tid, "code": code}, timeout=NET_TIMEOUT)
            data = r.json()
            if data.get("ok"):
                login = data.get("login") or ("tg_" + tid)
                token = data.get("token") or ""
                if rem.value:
                    page.client_storage.set("wb_u", login)
                    if token:
                        page.client_storage.set("wb_token", token)
            else:
                err = data.get("error", "Неверный код")
        except (requests.RequestException, ValueError):
            err = "Сервер недоступен"
        verify_btn.disabled = False
        verify_btn.content = ft.Text("Войти по коду", color="white", weight="bold")
        if login:
            enter(login, token)
            load()
        else:
            a_err.value = err
            page.update()

    def start_tg_login(e):
        a_err.value, a_err.color = "", DANGER
        tg_login_btn.disabled = True
        tg_login_btn.content = ft.Text("Открываю Telegram...", color="white", weight="bold")
        page.update()
        bg(_start_tg_login)

    def _start_tg_login():
        nonce, link, err = "", "", ""
        try:
            r = requests.post(API + S + "start_login", json={}, timeout=NET_TIMEOUT)
            d = r.json()
            if d.get("ok"):
                nonce = d.get("nonce") or ""
                link = d.get("url") or ""
            else:
                err = d.get("error") or "Ошибка сервера"
        except (requests.RequestException, ValueError):
            err = "Сервер недоступен"
        if not nonce:
            tg_login_btn.disabled = False
            tg_login_btn.content = tg_btn_txt
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
                r = requests.get(API + S + "poll_login", params={"nonce": nonce}, timeout=NET_TIMEOUT)
                d = r.json()
            except (requests.RequestException, ValueError):
                continue
            if d.get("ok") and d.get("token"):
                if rem.value:
                    page.client_storage.set("wb_u", d["login"])
                    page.client_storage.set("wb_token", d["token"])
                enter(d["login"], d["token"])
                load()
                return
        tg_login_btn.disabled = False
        tg_login_btn.content = tg_btn_txt
        a_err.value, a_err.color = "Время ожидания истекло. Нажмите кнопку ещё раз.", DANGER
        page.update()

    def toggle_mode(e):
        st["tg_mode"] = not st["tg_mode"]
        regular_box.visible = not st["tg_mode"]
        tg_box.visible = st["tg_mode"]
        mode_txt.value = "Войти через Telegram" if not st["tg_mode"] else "Обычный вход"
        a_err.value = ""
        page.update()

    send_btn.on_click = request_code
    tg_login_btn.on_click = start_tg_login
    verify_btn.on_click = verify_code
    mode_txt.on_click = toggle_mode

    auth_btn = ft.ElevatedButton(content=b_txt, bgcolor=P1, height=46, on_click=auth)

    regular_box = ft.Container(content=ft.Column([a_t, u_in, p_in, tg_in, rem, a_err, ft.Container(content=auth_btn, expand=True)], spacing=10), visible=True)
    bot_hint = ft.TextButton(content=ft.Text("Нет кода? Откройте @wb_jekich_bot и нажмите Start", size=11, color=P1), url="https://t.me/wb_jekich_bot", tooltip="Открыть бота в Telegram")
    tg_box = ft.Container(content=ft.Column([ft.Text("Вход через Telegram", size=16, weight="bold"), tg_login_btn, ft.Text("Если не сработало — введите логин и получите код:", size=11, color="#8A8A96"), tg_id_in, send_btn, code_in, verify_btn, a_err, bot_hint], spacing=10), visible=False)
    auth_view = ft.Container(padding=20, bgcolor=BG, expand=True, content=ft.Column([ft.Container(height=20), ft.Container(width=72, height=72, border_radius=20, gradient=ft.LinearGradient(colors=[P2, P1]), content=ft.Icon(ft.Icons.TELEGRAM, size=40, color="white"), alignment=ft.alignment.center), ft.Text("WB.Track", size=24, weight="bold", color="white"), regular_box, tg_box, ft.TextButton(content=mode_txt, on_click=toggle_mode)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10))

    # ---------- шапка ----------
    u_lbl = ft.Text("Кабинет", size=12, color="#E0E0E0")
    dot = ft.Icon(ft.Icons.CIRCLE, size=9, color="#00E676")
    st_lbl = ft.Text("Онлайн", size=11, color="white", weight="w500")
    spin = ft.ProgressRing(width=12, height=12, stroke_width=2, color="white", visible=False)
    badge = ft.Container(content=ft.Row([dot, spin, st_lbl], spacing=4), bgcolor="#26000000", padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=20)
    hdr = ft.Container(gradient=ft.LinearGradient(colors=[P2, P1]), padding=ft.padding.symmetric(horizontal=16, vertical=18), content=ft.Row([ft.Column([ft.Text("WB.Track", size=20, weight="bold", color="white"), u_lbl], expand=True, spacing=2), badge, ft.IconButton(icon=ft.Icons.SETTINGS_ROUNDED, icon_color="white", icon_size=20, on_click=lambda e: open_settings()), ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color="white", icon_size=20, on_click=lambda e: load(True))], spacing=6))

    # ---------- статистика ----------
    s1, s2, s3 = ft.Text("0", size=20, weight="bold", color="white"), ft.Text("0", size=20, weight="bold", color=P1), ft.Text("0", size=20, weight="bold", color=OK)
    stats = ft.Row([ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=14, border=ft.border.all(1, BORDER), content=ft.Column([s1, ft.Text("Всего", size=11, color="#8A8A94")], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)), ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=14, border=ft.border.all(1, BORDER), content=ft.Column([s2, ft.Text("В поиске", size=11, color="#8A8A94")], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)), ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=14, border=ft.border.all(1, BORDER), content=ft.Column([s3, ft.Text("Выкуплено", size=11, color="#8A8A94")], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2))], spacing=8)

    # ---------- список ----------
    sku_in = ft.TextField(hint_text="Артикул WB", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD)
    pr_in = ft.TextField(hint_text="Цена до (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, expand=True)
    lim_in = ft.TextField(value="1", prefix_text="Шт: ", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, width=105)
    srch = ft.TextField(hint_text="Поиск...", prefix_icon=ft.Icons.SEARCH_ROUNDED, border_radius=12, filled=True, bgcolor=CARD, on_change=lambda e: (st.update({"q": srch.value.lower()}), render(), page.update()))
    col = ft.Column(spacing=10)
    empty = ft.Container(visible=False, padding=40, content=ft.Column([ft.Icon(ft.Icons.INBOX_ROUNDED, size=56, color="#3A3A48"), ft.Text("Пока пусто", size=16, weight="bold", color="#8A8A94"), ft.Text("Добавьте артикул и цену — начнём следить", size=12, color="#5A5A66")], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6))

    def render():
        col.controls.clear()
        all_t = st["tasks"]
        s1.value, s2.value, s3.value = str(len(all_t)), str(len([t for t in all_t if t["bought"] < t["limit"]])), str(len([t for t in all_t if t["bought"] >= t["limit"]]))
        visible = [t for t in all_t if st["q"] in str(t["sku"]) or st["q"] in (t.get("name") or "").lower()]
        empty.visible = not visible
        for it in visible:
            sbp, wal, tgt = it.get("current_sbp"), it.get("current_wallet"), it["target_price"]
            bt = "✅ Выкуплено" if it["bought"] >= it["limit"] else (f"Еще -{sbp - tgt} ₽" if sbp and sbp > tgt else ("🔥 Цель!" if sbp else "⏳ Обновите"))
            ps = f"СБП: {sbp} ₽ • Кош: {wal} ₽" if sbp else "Цена не загружена"
            col.controls.append(ft.Container(bgcolor=CARD, padding=12, border_radius=16, border=ft.border.all(1, BORDER), content=ft.Row([ft.Container(content=ft.Image(src=it.get("image", ""), width=64, height=86, fit=ft.ImageFit.COVER), border_radius=10, clip_behavior=ft.ClipBehavior.ANTI_ALIAS), ft.Column([ft.Text(it.get("name") or str(it["sku"]), weight="bold", size=14, max_lines=2, color="white"), ft.Text(f"Арт: {it['sku']}", size=11, color="#8A8A94"), ft.Row([ft.Text((f"{sbp} ₽" if sbp else "—"), size=18, weight="bold", color=(OK if (sbp and sbp <= tgt) else WARN)), ft.Text((f"кош. {wal} ₽" if wal else ""), size=11, color="#8A8A94")], spacing=8), sparkline(it.get("history") or []), ft.Text(bt, size=11, color=P1, weight="w500"), ft.Text(f"Цель ≤ {tgt} ₽  ·  выкуплено {it['bought']}/{it['limit']}", size=11, color="#8A8A94")], expand=True, spacing=2), ft.Column([ft.IconButton(icon=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, icon_color=OK, icon_size=20, tooltip="Выкупить", visible=it["bought"] < it["limit"], on_click=lambda _, t=it: buy(t)), ft.IconButton(icon=ft.Icons.EDIT_ROUNDED, icon_color="#A0A0B0", icon_size=20, tooltip="Редактировать", on_click=lambda _, t=it: edit(t)), ft.IconButton(icon=ft.Icons.OPEN_IN_NEW_ROUNDED, icon_color="#A0A0B0", icon_size=20, tooltip="Открыть в WB", on_click=lambda _, s=it["sku"]: wb_open(page, s)), ft.IconButton(icon=ft.Icons.DELETE_ROUNDED, icon_color=DANGER, icon_size=20, on_click=lambda _, s=it["sku"]: bg(delete, s))], spacing=0)], spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)))

    def load(force=False):
        if st["busy"]:
            return
        busy(True, "Обновление...")
        bg(_load_request, force)

    def _load_request(force=False):
        try:
            r = requests.get(API + S + "tasks", params={"user": st["user"]}, headers=auth_headers(), timeout=NET_TIMEOUT)
            if r.status_code == 401:
                logout(None)
                return
            if r.status_code != 200:
                dot.color, st_lbl.value = "#FF5252", "Офлайн"
                page.update()
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
                    st_lbl.value = "Проверено " + txt
                    diff = time.time() - ts
                    dot.color = "#00E676" if diff < 3600 else ("#FFB300" if diff < 6 * 3600 else "#FF5252")
            except (requests.RequestException, ValueError, TypeError):
                pass
            reached = [t for t in tasks if t.get("current_sbp") and t["current_sbp"] <= t["target_price"] and (t.get("bought") or 0) < (t.get("limit") or 1)]
            if reached and not st.get("alerted_shown"):
                st["alerted_shown"] = True
                snack = ft.SnackBar(content=ft.Text(f"🔥 Цена достигнута: {reached[0].get('name', '')}", color="white", weight="bold"), bgcolor="#1B5E20", duration=4000)
                page.overlay.append(snack)
                snack.open = True
            render()
        except (requests.RequestException, ValueError):
            dot.color, st_lbl.value = "#FF5252", "Офлайн"
        finally:
            st["busy"] = False
            spin.visible = False
            if st_lbl.value.startswith("Обновление") or not st_lbl.value:
                st_lbl.value = "Онлайн"
            if st_lbl.value.startswith("Проверено") or st_lbl.value == "Онлайн":
                dot.color = "#00E676"
            page.update()

    def add(e):
        if st["busy"] or not sku_in.value or not pr_in.value:
            return
        try:
            sku, tgt, lim = int(sku_in.value.strip()), int(pr_in.value.strip()), int(lim_in.value.strip() or 1)
        except ValueError:
            return
        sku_in.value, pr_in.value = "", ""
        busy(True, "Добавление...")
        bg(_add_request, sku, tgt, lim)

    def _add_request(sku, tgt, lim):
        try:
            n, w, s, img = fetch_wb(sku)
            requests.post(API + S + "tasks", json={"owner": st["user"], "sku": sku, "target_price": tgt, "limit": lim, "name": n, "image": img, "current_sbp": s, "current_wallet": w}, headers=auth_headers(), timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    def delete(sku):
        try:
            requests.delete(API + S + "tasks" + S + str(sku), params={"user": st["user"]}, headers=auth_headers(), timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    def buy(task):
        """Отметить покупку: bought+1. Остальные поля шлём как есть, иначе сервер
        посчитает их пустыми и затрёт название/цены."""
        if st["busy"]:
            return
        busy(True, "Отмечаю...")
        bg(_buy_request, task, int(task.get("bought") or 0) + 1)

    def _buy_request(task, bought):
        payload = {"owner": st["user"], "sku": task["sku"], "bought": bought,
                   "target_price": task["target_price"], "limit": task.get("limit") or 1,
                   "name": task.get("name"), "image": task.get("image"),
                   "current_sbp": task.get("current_sbp"), "current_wallet": task.get("current_wallet")}
        try:
            requests.post(API + S + "tasks", json=payload, headers=auth_headers(), timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    def edit(task):
        pr_f = ft.TextField(value=str(task["target_price"]), label="Цена до (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD)
        lim_f = ft.TextField(value=str(task.get("limit") or 1), label="Кол-во (шт)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD)
        err = ft.Text("", size=12, color=DANGER)

        def save(e):
            try:
                tgt = int(pr_f.value.strip())
                lim = int(lim_f.value.strip() or 1)
            except ValueError:
                err.value = "Введите числа"
                page.update()
                return
            if tgt <= 0 or lim < 1:
                err.value = "Значения должны быть > 0"
                page.update()
                return
            dlg.open = False
            page.update()
            busy(True, "Сохраняю...")
            bg(_edit_request, task, tgt, lim)

        dlg = ft.AlertDialog(
            title=ft.Text(f"Редактировать {task['sku']}", weight="bold", size=16),
            content=ft.Column([pr_f, lim_f, err], spacing=10, tight=True),
            actions=[ft.TextButton(content=ft.Text("Отмена", color="#8A8A94"), on_click=lambda e: (setattr(dlg, "open", False), page.update())),
                     ft.ElevatedButton(content=ft.Text("Сохранить", color="white", weight="bold"), bgcolor=P1, on_click=save)],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def _edit_request(task, tgt, lim):
        payload = {"owner": st["user"], "sku": task["sku"], "target_price": tgt, "limit": lim,
                   "name": task.get("name"), "image": task.get("image"),
                   "current_sbp": task.get("current_sbp"), "current_wallet": task.get("current_wallet"),
                   "bought": task.get("bought") or 0}
        try:
            requests.post(API + S + "tasks", json=payload, headers=auth_headers(), timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    add_btn = ft.ElevatedButton(content=ft.Text("Добавить в отслеживание", color="white", weight="bold"), bgcolor=P1, height=46, on_click=add)
    main_b = ft.Column(visible=False, controls=[hdr, ft.Container(padding=14, content=ft.Column([stats, ft.Container(bgcolor=CARD, padding=12, border_radius=16, border=ft.border.all(1, BORDER), content=ft.Column([ft.Row([sku_in], spacing=8), ft.Row([pr_in, lim_in], spacing=8), ft.Container(content=add_btn, expand=True)], spacing=10)), srch, col, empty, ft.Text(f"WB.Track v{APP_VERSION}", size=10, color="#5A5A66", text_align=ft.TextAlign.CENTER)], spacing=12, horizontal_alignment=ft.CrossAxisAlignment.CENTER))])

    # ---------- обновление приложения ----------
    upd_txt = ft.Text("", size=12, color="white", expand=True)
    upd_bar = ft.Container(visible=False, bgcolor="#123B1E", padding=ft.padding.symmetric(horizontal=10, vertical=4),
                           content=ft.Row([ft.Icon(ft.Icons.SYSTEM_UPDATE_ROUNDED, size=16, color="#00E676"), upd_txt,
                                           ft.TextButton(content=ft.Text("Скачать", size=12, color="white", weight="bold"),
                                                         on_click=lambda e: page.launch_url(st["apk"]))], spacing=4))

    def check_update():
        try:
            r = requests.get(REL_URL, timeout=NET_TIMEOUT, headers={"Accept": "application/vnd.github+json"})
            if r.status_code != 200:
                return
            data = r.json()
            tag = (data.get("tag_name") or "").lstrip("v")
            apk = next((a.get("browser_download_url") for a in data.get("assets") or [] if (a.get("name") or "").endswith(".apk")), "")
            if not apk or vt(tag) <= vt(APP_VERSION):
                return
            st["apk"] = apk
            upd_txt.value = f"Доступна версия {tag}"
            upd_bar.visible = True
            page.update()
        except (requests.RequestException, ValueError, AttributeError):
            pass

    def open_settings():
        status_txt = ft.Text("", size=13, color=P1, weight="bold", opacity=0, animate_opacity=ft.Animation(400, "easeOut"), animate_scale=ft.Animation(400, "easeOut"))

        def change_password():
            old_f = ft.TextField(label="Старый пароль", password=True, can_reveal_password=True, border_radius=12, filled=True, bgcolor=CARD)
            new_f = ft.TextField(label="Новый пароль", password=True, can_reveal_password=True, border_radius=12, filled=True, bgcolor=CARD)
            err = ft.Text("", size=12, color=DANGER)
            def save(e):
                try:
                    r = requests.post(API + S + "change_password", json={"user": st["user"], "old_password": old_f.value.strip(), "new_password": new_f.value.strip()}, headers=auth_headers(), timeout=NET_TIMEOUT)
                    data = r.json()
                except (requests.RequestException, ValueError):
                    err.value = "Нет связи с сервером"
                    page.update()
                    return
                if not data.get("ok"):
                    err.value = data.get("error", "Ошибка")
                    page.update()
                    return
                dlg2.open = False
                page.update()
                snack = ft.SnackBar(content=ft.Text("Пароль изменён", color="white"), bgcolor="#1B5E20")
                page.overlay.append(snack)
                snack.open = True
                page.update()
            dlg2 = ft.AlertDialog(
                title=ft.Text("Смена пароля", weight="bold", size=16),
                content=ft.Column([old_f, new_f, err], spacing=10, tight=True),
                actions=[ft.TextButton(content=ft.Text("Отмена", color="#8A8A94"), on_click=lambda e: (setattr(dlg2, "open", False), page.update())),
                         ft.ElevatedButton(content=ft.Text("Сохранить", color="white", weight="bold"), bgcolor=P1, on_click=save)],
            )
            page.overlay.append(dlg2)
            dlg2.open = True
            page.update()

        def toggle_theme(e):
            cur = page.client_storage.get("wb_theme") or "dark"
            new = "light" if cur == "dark" else "dark"
            page.client_storage.set("wb_theme", new)
            snack = ft.SnackBar(content=ft.Text(f"Тема: {new}. Перезапустите приложение.", color="white"), bgcolor="#1B5E20")
            page.overlay.append(snack)
            snack.open = True
            page.update()

        def do_check():
            status_txt.opacity = 0
            status_txt.scale = 0.8
            spinner.visible = True
            status_txt.value = "Проверяю..."
            page.update()
            try:
                r = requests.get(REL_URL, timeout=NET_TIMEOUT, headers={"Accept": "application/vnd.github+json"})
                if r.status_code != 200:
                    status_txt.value = "Не удалось проверить"
                else:
                    data = r.json()
                    tag = (data.get("tag_name") or "").lstrip("v")
                    if vt(tag) <= vt(APP_VERSION):
                        status_txt.value = f"✓ У вас последняя версия ({APP_VERSION})"
                    else:
                        st["apk"] = next((a.get("browser_download_url") for a in data.get("assets") or [] if (a.get("name") or "").endswith(".apk")), "")
                        status_txt.value = f"Доступна {tag}"
                        upd_txt.value = f"Доступна версия {tag}"
                        upd_bar.visible = True
            except (requests.RequestException, ValueError, AttributeError):
                status_txt.value = "Нет связи с сервером"
            spinner.visible = False
            status_txt.opacity = 1
            status_txt.scale = 1.0
            page.update()

        cur_theme = page.client_storage.get("wb_theme") or "dark"
        theme_label = "Тёмная" if cur_theme == "dark" else "Светлая"

        spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=P1, visible=False)
        dlg = ft.AlertDialog(
            title=ft.Text("Настройки", weight="bold"),
            content=ft.Column([
                ft.Text("Аккаунт", size=12, weight="bold", color="#8A8A94"),
                ft.Text(f"Пользователь: {st['user'] or '—'}", size=12, color="#8A8A94"),
                ft.ElevatedButton(content=ft.Text("Сменить пароль", color="white", weight="bold"), bgcolor=CARD2, on_click=lambda e: change_password()),
                ft.ElevatedButton(content=ft.Text("Выйти", color=DANGER, weight="bold"), bgcolor=CARD2, on_click=lambda e: (setattr(dlg, "open", False), page.update(), logout(None))),
                ft.Divider(height=1, color=BORDER),
                ft.Text("Приложение", size=12, weight="bold", color="#8A8A94"),
                ft.Row([ft.ElevatedButton(content=ft.Text("Проверить обновления", color="white", weight="bold"), bgcolor=P1, on_click=lambda e: bg(do_check)), spinner], spacing=10),
                status_txt,
                ft.TextButton(content=ft.Text("Скачать обновление", color=P1), visible=bool(st.get("apk")), on_click=lambda e: page.launch_url(st["apk"])),
                ft.ElevatedButton(content=ft.Text(f"Тема: {theme_label} (переключить)", color="white", weight="bold"), bgcolor=CARD2, on_click=toggle_theme),
                ft.Divider(height=1, color=BORDER),
                ft.Text("О приложении", size=12, weight="bold", color="#8A8A94"),
                ft.Text("WB.Track — трекер цен Wildberries.", size=12, color="#8A8A94"),
                ft.Text("В разработке", size=11, color="#5A5A66", italic=True),
            ], spacing=8, tight=True),
            actions=[ft.TextButton(content=ft.Text("Закрыть", color=P1), on_click=lambda e: (setattr(dlg, "open", False), page.update()))],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    page.add(ft.Container(bgcolor=BG, expand=True, content=ft.Column([upd_bar, auth_view, main_b])))

    # первый экран уже нарисован — только теперь идём в сеть
    bg(check_update)
    saved = page.client_storage.get("wb_u") or ""
    saved_token = page.client_storage.get("wb_token") or ""
    if saved:
        enter(saved, saved_token)
        load()


if __name__ == "__main__":
    ft.app(target=main)

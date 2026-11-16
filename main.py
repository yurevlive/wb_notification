import flet as ft
import requests

S = chr(47)
API = "".join(["ht", "tps:", S, S, "yurevlive.", "pythonanywhere.", "com"])
WB = "".join(["ht", "tps:", S, S, "www.", "wildberries.", "ru", S, "catalog", S])
P1, P2, BG, CARD = "#CB11AB", "#481173", "#0E0E13", "#181820"

NET_TIMEOUT = 8

# Версия указывается здесь. Тег релиза (v1.0.1) обязан совпадать с ней —
# сборка упадёт, если не совпадает, иначе приложение зациклится на "Обновить".
APP_VERSION = "1.0.0"
REL_URL = "https://api.github.com/repos/yurevlive/wb_notification/releases/latest"


def vt(ver):
    """'1.0.10' -> (1, 0, 10) для правильного сравнения версий."""
    parts = []
    for p in str(ver).lstrip("v").split("."):
        parts.append(int(p) if p.isdigit() else 0)
    return tuple(parts + [0] * (3 - len(parts)))[:3]


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
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0
    page.scroll = ft.ScrollMode.AUTO
    page.locale_configuration = ft.LocaleConfiguration(supported_locales=[ft.Locale("ru", "RU")], current_locale=ft.Locale("ru", "RU"))
    st = {"tasks": [], "user": "", "reg": False, "q": "", "busy": False}

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

    def enter(u):
        st["user"] = u
        u_lbl.value = f"Кабинет: {u}"
        auth_view.visible, main_b.visible = False, True
        page.update()

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
        err, login = "", None
        try:
            r = requests.post(API + S + ("register" if st["reg"] else "login"),
                              json={"login": u, "password": p, "tg_id": tg_in.value.strip()},
                              timeout=NET_TIMEOUT)
            data = r.json()
            if data.get("ok"):
                login = data.get("login") or u
                if rem.value:
                    page.client_storage.set("wb_u", login)
            else:
                err = data.get("error", "Ошибка входа")
        except (requests.RequestException, ValueError):
            err = "Сервер недоступен, попробуйте позже"
        auth_btn.disabled = False
        b_txt.value = "Создать аккаунт" if st["reg"] else "Войти"
        if login:
            enter(login)
            load()
        else:
            a_err.value = err
            page.update()

    def logout(e):
        st["user"] = ""
        try:
            page.client_storage.remove("wb_u")
        except Exception:
            pass
        main_b.visible, auth_view.visible = False, True
        page.update()

    auth_btn = ft.ElevatedButton(content=b_txt, bgcolor=P1, height=46, on_click=auth)
    auth_view = ft.Container(padding=20, bgcolor=BG, expand=True, content=ft.Column([ft.Container(height=10), ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=56, color=P1), a_t, u_in, p_in, tg_in, rem, a_err, ft.Row([ft.Container(content=auth_btn, expand=True)]), ft.TextButton(content=sw_txt, on_click=toggle)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10))

    # ---------- шапка ----------
    u_lbl = ft.Text("Кабинет", size=12, color="#E0E0E0")
    dot = ft.Icon(ft.Icons.CIRCLE, size=9, color="#00E676")
    st_lbl = ft.Text("Онлайн", size=11, color="white", weight="w500")
    spin = ft.ProgressRing(width=12, height=12, stroke_width=2, color="white", visible=False)
    badge = ft.Container(content=ft.Row([dot, spin, st_lbl], spacing=4), bgcolor="#26000000", padding=ft.padding.symmetric(horizontal=8, vertical=4), border_radius=20)
    hdr = ft.Container(gradient=ft.LinearGradient(colors=[P2, P1]), padding=16, content=ft.Row([ft.Column([ft.Text("WB.Track [by.Жекич]", size=18, weight="bold"), u_lbl], expand=True), badge, ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color="white", on_click=lambda e: load(True)), ft.IconButton(icon=ft.Icons.LOGOUT_ROUNDED, icon_color="white", on_click=logout)], spacing=4))

    # ---------- статистика ----------
    s1, s2, s3 = ft.Text("0", size=16, weight="bold"), ft.Text("0", size=16, weight="bold", color="#E040FB"), ft.Text("0", size=16, weight="bold", color="#00E676")
    stats = ft.Row([ft.Container(expand=True, bgcolor=CARD, padding=8, border_radius=12, content=ft.Column([s1, ft.Text("Всего", size=11)], horizontal_alignment=ft.CrossAxisAlignment.CENTER)), ft.Container(expand=True, bgcolor=CARD, padding=8, border_radius=12, content=ft.Column([s2, ft.Text("В поиске", size=11)], horizontal_alignment=ft.CrossAxisAlignment.CENTER)), ft.Container(expand=True, bgcolor=CARD, padding=8, border_radius=12, content=ft.Column([s3, ft.Text("Выкуплено", size=11)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))], spacing=8)

    # ---------- список ----------
    sku_in = ft.TextField(hint_text="Артикул WB", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD)
    pr_in = ft.TextField(hint_text="Цена до (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, expand=True)
    lim_in = ft.TextField(value="1", prefix_text="Шт: ", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, width=105)
    srch = ft.TextField(hint_text="Поиск...", prefix_icon=ft.Icons.SEARCH_ROUNDED, border_radius=12, filled=True, bgcolor=CARD, on_change=lambda e: (st.update({"q": srch.value.lower()}), render(), page.update()))
    col = ft.Column(spacing=10)
    empty = ft.Container(visible=False, padding=30, content=ft.Column([ft.Icon(ft.Icons.INBOX_ROUNDED, size=42, color="#4A4A55"), ft.Text("Пока пусто — добавьте артикул", size=13, color="#8A8A94")], horizontal_alignment=ft.CrossAxisAlignment.CENTER))

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
            col.controls.append(ft.Container(bgcolor=CARD, padding=10, border_radius=14, content=ft.Row([ft.Image(src=it.get("image", ""), width=56, height=76, fit=ft.ImageFit.COVER), ft.Column([ft.Text(it.get("name") or str(it["sku"]), weight="bold", size=13, max_lines=2), ft.Text(f"Арт: {it['sku']} • {bt}", size=11, color="#E040FB"), ft.Text(ps, size=12, color="#00E676"), ft.Text(f"Цель: до {tgt} ₽ ({it['bought']}/{it['limit']})", size=11)], expand=True, spacing=2), ft.Column([ft.IconButton(icon=ft.Icons.OPEN_IN_NEW_ROUNDED, icon_size=18, on_click=lambda _, s=it["sku"]: page.launch_url(WB + str(s) + S + "detail.aspx")), ft.IconButton(icon=ft.Icons.DELETE_ROUNDED, icon_color="#FF5252", icon_size=18, on_click=lambda _, s=it["sku"]: bg(delete, s))], spacing=0)])))

    def load(force=False):
        if st["busy"]:
            return
        busy(True, "Обновление...")
        bg(_load_request, force)

    def _load_request(force=False):
        try:
            r = requests.get(API + S + "tasks", params={"user": st["user"]}, timeout=NET_TIMEOUT)
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
            render()
        except (requests.RequestException, ValueError):
            dot.color, st_lbl.value = "#FF5252", "Офлайн"
        finally:
            st["busy"] = False
            spin.visible = False
            if st_lbl.value == "Онлайн":
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
            requests.post(API + S + "tasks", json={"owner": st["user"], "sku": sku, "target_price": tgt, "limit": lim, "name": n, "image": img, "current_sbp": s, "current_wallet": w}, timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    def delete(sku):
        try:
            requests.delete(API + S + "tasks" + S + str(sku), params={"user": st["user"]}, timeout=NET_TIMEOUT)
        except (requests.RequestException, ValueError):
            pass
        st["busy"] = False
        load()

    add_btn = ft.ElevatedButton(content=ft.Text("Добавить в отслеживание", color="white", weight="bold"), bgcolor=P1, height=46, on_click=add)
    main_b = ft.Column(visible=False, controls=[hdr, ft.Container(padding=14, content=ft.Column([stats, sku_in, ft.Row([pr_in, lim_in], spacing=8), ft.Row([ft.Container(content=add_btn, expand=True)]), srch, col, empty], spacing=10))])

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

    page.add(ft.Container(bgcolor=BG, expand=True, content=ft.Column([upd_bar, auth_view, main_b])))

    # первый экран уже нарисован — только теперь идём в сеть
    bg(check_update)
    saved = page.client_storage.get("wb_u") or ""
    if saved:
        enter(saved)
        load()


ft.app(target=main)

import threading
import flet as ft
import requests

S = chr(47)
API = "".join(["ht", "tps:", S, S, "yurevlive.", "pythonanywhere.", "com"])
WB_URL = "".join(["ht", "tps:", S, S, "www.", "wildberries.", "ru", S, "catalog", S])
P1, P2, BG, CARD, BORDER = "#CB11AB", "#481173", "#0E0E13", "#181820", "#282834"
COEF_WALLET, COEF_SBP = 426 / 395, 454 / 395

def get_basket_host(vol):
    limits = (143, 287, 431, 719, 1007, 1061, 1115, 1169, 1313, 1601, 1655, 1919, 2045, 2189, 2405, 2621, 2837, 3053, 3269, 3485, 3701, 3917, 4133, 4349, 4565, 4877, 5189, 5501, 5813, 6125, 6437, 6749, 7061, 7373, 7685)
    for i, lim in enumerate(limits, 1):
        if vol <= lim:
            return f"{i:02d}"
    return "36"

def fetch_wb_direct(sku):
    vol, part = sku // 100000, sku // 1000
    host = get_basket_host(vol)
    base = "".join(["ht", "tps:", S, S, f"basket-{host}.", "wbbasket.", "ru", S, f"vol{vol}", S, f"part{part}", S, str(sku)])
    img = base + S + "images" + S + "c246x328" + S + "1.webp"
    hdr = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"}
    name, w_pr, s_pr = f"Товар {sku}", None, None
    try:
        rc = requests.get(base + S + "info" + S + "ru" + S + "card.json", headers=hdr, timeout=6)
        if rc.status_code == 200:
            name = rc.json().get("imt_name") or name
        rp = requests.get(base + S + "info" + S + "price-history.json", headers=hdr, timeout=6)
        if rp.status_code == 200 and rp.json():
            base_rub = rp.json()[-1].get("price", {}).get("RUB", 0) // 100
            if base_rub > 0:
                w_pr, s_pr = round(base_rub * COEF_WALLET), round(base_rub * COEF_SBP)
    except Exception:
        pass
    return name, w_pr, s_pr, img

def main(page: ft.Page):
    page.title = "WB.Track [by.Жекич]"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor, page.padding, page.scroll = BG, 0, "adaptive"
    page.locale_configuration = ft.LocaleConfiguration(supported_locales=[ft.Locale("ru", "RU")], current_locale=ft.Locale("ru", "RU"))
    st = {"mode": "all", "tasks": [], "user": "", "reg": False, "query": ""}

    splash = ft.Container(height=620, bgcolor=BG, alignment=ft.alignment.center, content=ft.Column([
        ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=64, color=P1),
        ft.Text("WB.Track", size=38, weight="bold", color="white"),
        ft.Text("[by.Жекич]", size=18, color="#E040FB")
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    a_title = ft.Text("Вход в кабинет", size=24, weight="bold", color="white")
    u_in = ft.TextField(hint_text="Логин", prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED, border_radius=12, filled=True, bgcolor=CARD)
    p_in = ft.TextField(hint_text="Пароль", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED, border_radius=12, filled=True, bgcolor=CARD)
    tg_in = ft.TextField(hint_text="Числовой Telegram ID", prefix_icon=ft.Icons.SEND_ROUNDED, border_radius=12, filled=True, bgcolor=CARD, visible=False)
    rem_chk = ft.Checkbox(label="Запомнить меня", value=True, active_color=P1)
    a_err = ft.Text("", size=13, color="#FF5252")
    a_btn_t = ft.Text("Войти", color="white", weight="bold")
    sw_t = ft.Text("Нет аккаунта? Регистрация", size=13, color="#E040FB")

    def toggle(e):
        st["reg"] = not st["reg"]
        a_title.value = "Регистрация" if st["reg"] else "Вход в кабинет"
        a_btn_t.value = "Создать аккаунт" if st["reg"] else "Войти"
        sw_t.value = "Уже есть аккаунт? Войти" if st["reg"] else "Нет аккаунта? Регистрация"
        tg_in.visible, a_err.value = st["reg"], ""
        page.update()

    def enter_cabinet(username):
        st["user"] = username
        u_lbl.value = f"Профиль: {username}"
        auth_box.visible, main_box.visible = False, True
        load()

    def auth(e):
        u, p = u_in.value.strip().lower(), p_in.value.strip()
        if not u or not p:
            a_err.value = "Введите логин и пароль"
            page.update()
            return
        ep = "register" if st["reg"] else "login"
        try:
            r = requests.post(API + S + ep, json={"login": u, "password": p, "tg_id": tg_in.value.strip()}, timeout=10).json()
            if r.get("ok"):
                if rem_chk.value:
                    page.client_storage.set("wb_saved_user", r["login"])
                enter_cabinet(r["login"])
                return
            a_err.value = r.get("error", "Ошибка")
        except Exception as ex:
            a_err.value = f"Ошибка сети: {ex}"
        page.update()

    auth_box = ft.Container(visible=False, padding=24, content=ft.Column([
        ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=64, color=P1), a_title, u_in, p_in, tg_in, rem_chk, a_err,
        ft.ElevatedButton(content=a_btn_t, bgcolor=P1, height=48, width=320, on_click=auth),
        ft.TextButton(content=sw_t, on_click=toggle)
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10))

    def logout(e):
        st["user"], st["tasks"] = "", []
        page.client_storage.remove("wb_saved_user")
        main_box.visible, auth_box.visible = False, True
        page.update()

    u_lbl = ft.Text("Кабинет", size=12, color="#E0E0E0")
    dot = ft.Icon(ft.Icons.CIRCLE, size=9, color="#00E676")
    lbl = ft.Text("Онлайн", size=11, color="white")
    hdr = ft.Container(gradient=ft.LinearGradient(colors=[P2, P1]), padding=18, content=ft.Row([
        ft.Column([ft.Text("WB.Track [by.Жекич]", size=19, weight="bold", color="white"), u_lbl], expand=True),
        ft.Row([dot, lbl], spacing=4),
        ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color="white", on_click=lambda e: load(True)),
        ft.IconButton(icon=ft.Icons.LOGOUT_ROUNDED, icon_color="white", on_click=logout)
    ]))

    s_tot, s_act, s_done = ft.Text("0", size=18, weight="bold"), ft.Text("0", size=18, weight="bold", color="#E040FB"), ft.Text("0", size=18, weight="bold", color="#00E676")
    stats = ft.Row([
        ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=12, content=ft.Column([s_tot, ft.Text("Всего", size=11, color="#8E8E9E")], horizontal_alignment=ft.CrossAxisAlignment.CENTER)),
        ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=12, content=ft.Column([s_act, ft.Text("В поиске", size=11, color="#8E8E9E")], horizontal_alignment=ft.CrossAxisAlignment.CENTER)),
        ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=12, content=ft.Column([s_done, ft.Text("Выкуплено", size=11, color="#8E8E9E")], horizontal_alignment=ft.CrossAxisAlignment.CENTER))
    ], spacing=8)

    sku_in = ft.TextField(hint_text="Артикул WB", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD)
    pr_in = ft.TextField(hint_text="Цена до (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, expand=True)
    lim_in = ft.TextField(value="1", prefix_text="Шт: ", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, width=120)
    search_in = ft.TextField(hint_text="Поиск...", prefix_icon=ft.Icons.SEARCH_ROUNDED, border_radius=12, filled=True, bgcolor=CARD, height=42, on_change=lambda e: (st.update({"query": search_in.value.lower()}), render(), page.update()))
    col = ft.Column(spacing=10)

    def render():
        col.controls.clear()
        all_t = st["tasks"]
        act_t = [t for t in all_t if t["bought"] < t["limit"]]
        done_t = [t for t in all_t if t["bought"] >= t["limit"]]
        s_tot.value, s_act.value, s_done.value = str(len(all_t)), str(len(act_t)), str(len(done_t))
        items = [t for t in all_t if st["query"] in str(t["sku"]) or st["query"] in (t.get("name") or "").lower()]
        for it in items:
            sbp, wal, tgt = it.get("current_sbp"), it.get("current_wallet"), it["target_price"]
            badge_t = "✅ Выкуплено" if it["bought"] >= it["limit"] else (f"Еще -{sbp - tgt} ₽" if sbp and sbp > tgt else ("🔥 Цель!" if sbp else "⏳ Обновите"))
            p_s = f"СБП: {sbp} ₽ • Кош: {wal} ₽" if sbp else "Цена не загружена"
            img = ft.Image(src=it.get("image", ""), width=60, height=80, fit=ft.ImageFit.COVER)
            info = ft.Column([
                ft.Text(it.get("name") or f"Товар {it['sku']}", weight="bold", size=14, max_lines=2),
                ft.Text(f"Арт: {it['sku']} • {badge_t}", size=11, color="#E040FB"),
                ft.Text(p_s, size=12, color="#00E676"),
                ft.Text(f"Цель: до {tgt} ₽ ({it['bought']}/{it['limit']})", size=11, color="#B0B0C0")
            ], expand=True, spacing=2)
            btns = ft.Column([
                ft.IconButton(icon=ft.Icons.OPEN_IN_NEW_ROUNDED, icon_size=18, on_click=lambda _, s=it["sku"]: page.launch_url(WB_URL + str(s) + S + "detail.aspx")),
                ft.IconButton(icon=ft.Icons.DELETE_ROUNDED, icon_color="#FF5252", icon_size=18, on_click=lambda _, s=it["sku"]: delete(s))
            ], spacing=0)
            col.controls.append(ft.Container(bgcolor=CARD, padding=10, border_radius=14, content=ft.Row([img, info, btns])))

    def load(force=False):
        r = requests.get(API + S + "tasks", params={"user": st["user"]}, timeout=10)
        if r.status_code == 200:
            tasks = r.json()
            for t in tasks:
                if force or not t.get("current_sbp"):
                    name, w_pr, s_pr, img = fetch_wb_direct(t["sku"])
                    if s_pr:
                        t["name"], t["current_wallet"], t["current_sbp"], t["image"] = name, w_pr, s_pr, img
                        requests.post(API + S + "tasks", json=t, timeout=6)
            st["tasks"] = tasks
            dot.color, lbl.value = "#00E676", "Онлайн"
            render()
        page.update()

    def add(e):
        if sku_in.value and pr_in.value:
            sku, tgt, lim = int(sku_in.value.strip()), int(pr_in.value.strip()), int(lim_in.value.strip() or 1)

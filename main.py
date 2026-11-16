import flet as ft
import requests

S = chr(47)
API = "".join(["ht", "tps:", S, S, "yurevlive.", "pythonanywhere.", "com"])
WB = "".join(["ht", "tps:", S, S, "www.", "wildberries.", "ru", S, "catalog", S])
P1, P2, BG, CARD = "#CB11AB", "#481173", "#0E0E13", "#181820"

def fetch_wb(sku):
    vol, part = sku // 100000, sku // 1000
    lims = (143,287,431,719,1007,1061,1115,1169,1313,1601,1655,1919,2045,2189,2405,2621,2837,3053,3269,3485,3701,3917,4133,4349,4565,4877,5189,5501,5813,6125,6437,6749,7061,7373,7685)
    h = "36"
    for i, l in enumerate(lims, 1):
        if vol <= l:
            h = f"{i:02d}"
            break
    base = "".join(["ht", "tps:", S, S, f"basket-{h}.", "wbbasket.", "ru", S, f"vol{vol}", S, f"part{part}", S, str(sku)])
    img = base + S + "images" + S + "c246x328" + S + "1.webp"
    name, w_pr, s_pr = f"Товар {sku}", None, None
    try:
        rc = requests.get(base + S + "info" + S + "ru" + S + "card.json", timeout=6)
        if rc.status_code == 200: name = rc.json().get("imt_name") or name
        rp = requests.get(base + S + "info" + S + "price-history.json", timeout=6)
        if rp.status_code == 200 and rp.json():
            rub = rp.json()[-1].get("price", {}).get("RUB", 0) // 100
            if rub > 0: w_pr, s_pr = round(rub * 426 / 395), round(rub * 454 / 395)
    except Exception: pass
    return name, w_pr, s_pr, img

def main(page: ft.Page):
    page.title = "WB.Track [by.Жекич]"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor, page.padding = BG, 0
    page.locale_configuration = ft.LocaleConfiguration(supported_locales=[ft.Locale("ru", "RU")], current_locale=ft.Locale("ru", "RU"))
    st = {"tasks": [], "user": "", "reg": False, "q": ""}

    a_t = ft.Text("Вход в кабинет", size=24, weight="bold")
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
        load()

    def auth(e):
        u, p = u_in.value.strip().lower(), p_in.value.strip()
        if not u or not p: return
        r = requests.post(API + S + ("register" if st["reg"] else "login"), json={"login": u, "password": p, "tg_id": tg_in.value.strip()}, timeout=10).json()
        if r.get("ok"):
            if rem.value: page.client_storage.set("wb_u", r["login"])
            enter(r["login"])
        else:
            a_err.value = r.get("error", "Ошибка")
            page.update()

    def logout(e):
        st["user"] = ""
        page.client_storage.remove("wb_u")
        main_b.visible, auth_view.visible = False, True
        page.update()

    auth_view = ft.Container(padding=24, content=ft.Column([ft.Container(height=20), ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=64, color=P1), a_t, u_in, p_in, tg_in, rem, a_err, ft.ElevatedButton(content=b_txt, bgcolor=P1, height=48, width=320, on_click=auth), ft.TextButton(content=sw_txt, on_click=toggle)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10))

    u_lbl = ft.Text("Кабинет", size=12, color="#E0E0E0")
    hdr = ft.Container(gradient=ft.LinearGradient(colors=[P2, P1]), padding=18, content=ft.Row([ft.Column([ft.Text("WB.Track [by.Жекич]", size=19, weight="bold"), u_lbl], expand=True), ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color="white", on_click=lambda e: load(True)), ft.IconButton(icon=ft.Icons.LOGOUT_ROUNDED, icon_color="white", on_click=logout)]))
    s1, s2, s3 = ft.Text("0", size=18, weight="bold"), ft.Text("0", size=18, weight="bold", color="#E040FB"), ft.Text("0", size=18, weight="bold", color="#00E676")
    stats = ft.Row([ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=12, content=ft.Column([s1, ft.Text("Всего", size=11)], horizontal_alignment=ft.CrossAxisAlignment.CENTER)), ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=12, content=ft.Column([s2, ft.Text("В поиске", size=11)], horizontal_alignment=ft.CrossAxisAlignment.CENTER)), ft.Container(expand=True, bgcolor=CARD, padding=10, border_radius=12, content=ft.Column([s3, ft.Text("Выкуплено", size=11)], horizontal_alignment=ft.CrossAxisAlignment.CENTER))], spacing=8)

    sku_in = ft.TextField(hint_text="Артикул WB", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD)
    pr_in = ft.TextField(hint_text="Цена до (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, expand=True)
    lim_in = ft.TextField(value="1", prefix_text="Шт: ", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, width=120)
    srch = ft.TextField(hint_text="Поиск...", prefix_icon=ft.Icons.SEARCH_ROUNDED, border_radius=12, filled=True, bgcolor=CARD, height=42, on_change=lambda e: (st.update({"q": srch.value.lower()}), render(), page.update()))
    col = ft.Column(spacing=10)

    def render():
        col.controls.clear()
        all_t = st["tasks"]
        s1.value, s2.value, s3.value = str(len(all_t)), str(len([t for t in all_t if t["bought"] < t["limit"]])), str(len([t for t in all_t if t["bought"] >= t["limit"]]))
        for it in [t for t in all_t if st["q"] in str(t["sku"]) or st["q"] in (t.get("name") or "").lower()]:
            sbp, wal, tgt = it.get("current_sbp"), it.get("current_wallet"), it["target_price"]
            bt = "✅ Выкуплено" if it["bought"] >= it["limit"] else (f"Еще -{sbp - tgt} ₽" if sbp and sbp > tgt else ("🔥 Цель!" if sbp else "⏳ Обновите"))
            ps = f"СБП: {sbp} ₽ • Кош: {wal} ₽" if sbp else "Цена не загружена"
            col.controls.append(ft.Container(bgcolor=CARD, padding=10, border_radius=14, content=ft.Row([ft.Image(src=it.get("image", ""), width=60, height=80, fit=ft.ImageFit.COVER), ft.Column([ft.Text(it.get("name") or str(it["sku"]), weight="bold", size=14, max_lines=2), ft.Text(f"Арт: {it['sku']} • {bt}", size=11, color="#E040FB"), ft.Text(ps, size=12, color="#00E676"), ft.Text(f"Цель: до {tgt} ₽ ({it['bought']}/{it['limit']})", size=11)], expand=True, spacing=2), ft.Column([ft.IconButton(icon=ft.Icons.OPEN_IN_NEW_ROUNDED, icon_size=18, on_click=lambda _, s=it["sku"]: page.launch_url(WB + str(s) + S + "detail.aspx")), ft.IconButton(icon=ft.Icons.DELETE_ROUNDED, icon_color="#FF5252", icon_size=18, on_click=lambda _, s=it["sku"]: delete(s))], spacing=0)])))

    def load(force=False):
        r = requests.get(API + S + "tasks", params={"user": st["user"]}, timeout=10)
        if r.status_code == 200:
            tasks = r.json()
            for t in tasks:
                if force or not t.get("current_sbp"):
                    n, w, s, img = fetch_wb(t["sku"])
                    if s:
                        t["name"], t["current_wallet"], t["current_sbp"], t["image"] = n, w, s, img
                        requests.post(API + S + "tasks", json=t, timeout=6)
            st["tasks"] = tasks
            render()
        page.update()

    def add(e):
        if sku_in.value and pr_in.value:
            sku, tgt, lim = int(sku_in.value.strip()), int(pr_in.value.strip()), int(lim_in.value.strip() or 1)
            n, w, s, img = fetch_wb(sku)
            requests.post(API + S + "tasks", json={"owner": st["user"], "sku": sku, "target_price": tgt, "limit": lim, "name": n, "image": img, "current_sbp": s, "current_wallet": w}, timeout=10)
            sku_in.value, pr_in.value = "", ""
            load()

    def delete(sku):
        requests.delete(API + S + "tasks" + S + str(sku), params={"user": st["user"]}, timeout=10)
        load()

    main_b = ft.ListView(visible=False, expand=True, padding=0, controls=[hdr, ft.Container(padding=14, content=ft.Column([stats, sku_in, ft.Row([pr_in, lim_in]), ft.ElevatedButton(content=ft.Text("Добавить в отслеживание", color="white", weight="bold"), bgcolor=P1, height=46, width=340, on_click=add), srch, col], spacing=10))])
    page.add(auth_view, main_b)
    saved = page.client_storage.get("wb_u") or ""
    if saved: enter(saved)

ft.app(target=main)

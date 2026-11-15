import threading
import flet as ft
import requests

S = chr(47)
API_URL = "".join(["ht", "tps:", S, S, "yurevlive.", "pythonanywhere.", "com"])
WB_PURPLE = "#CB11AB"
WB_DARK = "#481173"
BG_COLOR = "#121216"
CARD_COLOR = "#1E1E26"

def main(page: ft.Page):
    page.title = "WB.Track [by.Жекич]"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG_COLOR
    page.padding = 0
    page.scroll = "adaptive"

    state = {"mode": "all", "tasks": [], "user": "", "auth_mode": "login"}

    # 1. ЗАСТАВКА
    splash = ft.Container(
        height=620, bgcolor=BG_COLOR, alignment=ft.alignment.center,
        content=ft.Column([
            ft.Container(width=84, height=84, border_radius=24, gradient=ft.LinearGradient(colors=[WB_PURPLE, "#7C3AED"]), alignment=ft.alignment.center, content=ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=46, color="white")),
            ft.Text("WB.Track", size=38, weight="bold", color="white"),
            ft.Text("[by.Жекич]", size=18, weight="w500", color="#E040FB")
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)
    )

    # 2. ЭКРАН ЛИЧНОГО КАБИНЕТА (ВХОД / РЕГИСТРАЦИЯ)
    auth_title = ft.Text("Вход в кабинет", size=24, weight="bold", color="white")
    login_in = ft.TextField(hint_text="Логин (от 3 символов)", prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE)
    pass_in = ft.TextField(hint_text="Пароль (от 4 символов)", password=True, can_reveal_password=True, prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE)
    tg_in = ft.TextField(hint_text="Telegram ID для уведомлений (необязательно)", prefix_icon=ft.Icons.SEND_ROUNDED, keyboard_type=ft.KeyboardType.NUMBER, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE, visible=False)
    auth_err = ft.Text("", size=13, color="#FF5252")
    auth_btn_txt = ft.Text("Войти", color="white", weight="bold", size=15)
    switch_txt = ft.Text("Нет аккаунта? Зарегистрироваться", size=13, color="#E040FB")

    def toggle_auth_mode(e):
        is_reg = state["auth_mode"] == "login"
        state["auth_mode"] = "register" if is_reg else "login"
        auth_title.value = "Регистрация" if is_reg else "Вход в кабинет"
        auth_btn_txt.value = "Создать аккаунт" if is_reg else "Войти"
        switch_txt.value = "Уже есть аккаунт? Войти" if is_reg else "Нет аккаунта? Зарегистрироваться"
        tg_in.visible = is_reg
        auth_err.value = ""
        page.update()

    def submit_auth(e):
        u, p = login_in.value.strip().lower(), pass_in.value.strip()
        if not u or not p:
            auth_err.value = "Введите логин и пароль"
            page.update()
            return
        auth_err.value, auth_err.color = "⏳ Подключение...", "#E040FB"
        page.update()
        endpoint = "register" if state["auth_mode"] == "register" else "login"
        payload = {"login": u, "password": p, "tg_id": tg_in.value.strip()}
        try:
            r = requests.post(API_URL + S + endpoint, json=payload, timeout=8)
            res = r.json()
            if res.get("ok"):
                state["user"] = res["login"]
                page.client_storage.set("wb_user", res["login"])
                open_dashboard()
            else:
                auth_err.value, auth_err.color = f"⚠️ {res.get('error', 'Ошибка')}", "#FF5252"
                page.update()
        except Exception as err:
            auth_err.value, auth_err.color = f"⚠️ Ошибка сети: {err}", "#FF5252"
            page.update()

    auth_btn = ft.Container(gradient=ft.LinearGradient(colors=[WB_PURPLE, "#9C27B0"]), border_radius=14, height=50, alignment=ft.alignment.center, ink=True, on_click=submit_auth, content=auth_btn_txt)
    auth_view = ft.Container(
        visible=False, padding=24,
        content=ft.Column([
            ft.Container(height=30),
            ft.Icon(ft.Icons.ACCOUNT_CIRCLE_ROUNDED, size=72, color=WB_PURPLE),
            auth_title,
            ft.Text("Личный трекер цен Wildberries", size=13, color="#8E8E9E"),
            ft.Container(height=10),
            login_in, pass_in, tg_in, auth_err, auth_btn,
            ft.Container(height=8),
            ft.Container(content=switch_txt, on_click=toggle_auth_mode, padding=8)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12)
    )

    # 3. ГЛАВНЫЙ ЭКРАН ТРЕКЕРА
    user_lbl = ft.Text("Кабинет", size=12, color="#E0E0E0")
    dot = ft.Icon(ft.Icons.CIRCLE, size=10, color="#00E676")
    lbl = ft.Text("Онлайн", size=12, color="white", weight="w500")
    badge = ft.Container(content=ft.Row([dot, lbl], spacing=5), bgcolor="#2A1B3D", padding=ft.padding.symmetric(horizontal=10, vertical=5), border_radius=20)

    def logout(e):
        state["user"] = ""
        page.client_storage.remove("wb_user")
        main_view.visible = False
        auth_view.visible = True
        page.update()

    header = ft.Container(
        gradient=ft.LinearGradient(colors=[WB_DARK, WB_PURPLE]),
        padding=ft.padding.only(left=20, right=12, top=35, bottom=20),
        border_radius=ft.border_radius.only(bottom_left=24, bottom_right=24),
        content=ft.Row([
            ft.Column([ft.Text("WB.Track [by.Жекич]", size=20, weight="bold", color="white"), user_lbl], expand=True, spacing=2),
            badge,
            ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color="white", bgcolor="#33FFFFFF", on_click=lambda e: load_list()),
            ft.IconButton(icon=ft.Icons.LOGOUT_ROUNDED, icon_color="white", bgcolor="#33FFFFFF", tooltip="Выйти", on_click=logout)
        ], spacing=6)
    )

    sku_in = ft.TextField(hint_text="Артикул WB", prefix_icon=ft.Icons.QR_CODE_2_ROUNDED, keyboard_type=ft.KeyboardType.NUMBER, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE)
    price_in = ft.TextField(hint_text="Цена до (₽)", prefix_icon=ft.Icons.CURRENCY_RUBLE_ROUNDED, keyboard_type=ft.KeyboardType.NUMBER, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE, expand=True)
    limit_in = ft.TextField(value="1", prefix_text="Шт: ", prefix_icon=ft.Icons.SHOPPING_BAG_OUTLINED, keyboard_type=ft.KeyboardType.NUMBER, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE, width=155)
    status_txt = ft.Text("", size=13, weight="w500")
    tasks_col = ft.Column(spacing=12)

    t_all = ft.Text("Все (0)", size=13, weight="bold", color="white")
    t_act = ft.Text("Активные (0)", size=13, color="#A0A0B0")
    t_done = ft.Text("Выкупленные (0)", size=13, color="#A0A0B0")
    b_all = ft.Container(content=t_all, bgcolor=WB_PURPLE, padding=ft.padding.symmetric(horizontal=14, vertical=8), border_radius=20, on_click=lambda e: set_tab("all"))
    b_act = ft.Container(content=t_act, bgcolor=CARD_COLOR, padding=ft.padding.symmetric(horizontal=14, vertical=8), border_radius=20, on_click=lambda e: set_tab("active"))
    b_done = ft.Container(content=t_done, bgcolor=CARD_COLOR, padding=ft.padding.symmetric(horizontal=14, vertical=8), border_radius=20, on_click=lambda e: set_tab("done"))

    def set_tab(m):
        state["mode"] = m
        for btn, txt, key in [(b_all, t_all, "all"), (b_act, t_act, "active"), (b_done, t_done, "done")]:
            btn.bgcolor = WB_PURPLE if m == key else CARD_COLOR
            txt.color = "white" if m == key else "#A0A0B0"
            txt.weight = "bold" if m == key else "w500"
        render()
        page.update()

    def render():
        tasks_col.controls.clear()
        all_t = state["tasks"]
        act_t = [t for t in all_t if t["bought"] < t["limit"]]
        done_t = [t for t in all_t if t["bought"] >= t["limit"]]
        t_all.value, t_act.value, t_done.value = f"Все ({len(all_t)})", f"Активные ({len(act_t)})", f"Выкупленные ({len(done_t)})"
        items = act_t if state["mode"] == "active" else (done_t if state["mode"] == "done" else all_t)
        if not items:
            tasks_col.controls.append(ft.Container(bgcolor=CARD_COLOR, padding=25, border_radius=16, alignment=ft.alignment.center, content=ft.Text("Ваш список пуст", color="#888899")))
            return
        for it in items:
            done = it["bought"] >= it["limit"]
            chip = ft.Container(content=ft.Text("✅ Выкуплено" if done else "⏳ Поиск", size=10, color="#00E676" if done else "#E040FB", weight="bold"), bgcolor="#1B3B2B" if done else "#2D1B3D", padding=ft.padding.symmetric(horizontal=7, vertical=2), border_radius=6)
            img = ft.Image(src=it.get("image", ""), width=68, height=88, fit=ft.ImageFit.COVER, error_content=ft.Icon(ft.Icons.SHOPPING_BAG_OUTLINED, color="#666677"))
            thumb = ft.Container(width=68, height=88, border_radius=12, bgcolor="#2A2A35", clip_behavior=ft.ClipBehavior.HARD_EDGE, content=img)
            p_str = f"Сейчас: {it.get('current_sbp')} ₽ (СБП) • {it.get('current_wallet')} ₽ (Кош.)" if it.get("current_sbp") else "Загрузка цены..."
            info = ft.Column([
                ft.Text(it.get("name") or f"Товар {it['sku']}", weight="bold", size=14, color="white", max_lines=2),
                ft.Row([ft.Text(f"Арт: {it['sku']}", size=11, color="#8E8E9E"), chip], spacing=6),
                ft.Text(p_str, size=12, color="#00E676", weight="w500"),
                ft.Text(f"Цель: до {it['target_price']} ₽ • Куплено: {it['bought']}/{it['limit']}", size=12, color="#B0B0C0")
            ], expand=True, spacing=3)
            del_b = ft.IconButton(icon=ft.Icons.DELETE_ROUNDED, icon_color="#FF5252", bgcolor="#26FF5252", on_click=lambda _, s=it["sku"]: del_item(s))

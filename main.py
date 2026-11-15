import threading
import flet as ft
import requests

S = chr(47)
API = "".join(["ht", "tps:", S, S, "yurevlive.", "pythonanywhere.", "com"])
P1, P2, BG, CARD = "#CB11AB", "#481173", "#121216", "#1E1E26"

def main(page: ft.Page):
    page.title = "WB.Track [by.Жекич]"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor, page.padding, page.scroll = BG, 0, "adaptive"
    st = {"mode": "all", "tasks": [], "user": "", "reg": False}

    splash = ft.Container(height=620, bgcolor=BG, alignment=ft.alignment.center, content=ft.Column([
        ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=64, color=P1),
        ft.Text("WB.Track", size=38, weight="bold", color="white"),
        ft.Text("[by.Жекич]", size=18, color="#E040FB")
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    a_title = ft.Text("Вход в кабинет", size=24, weight="bold", color="white")
    u_in = ft.TextField(hint_text="Логин", border_radius=12, filled=True, bgcolor=CARD)
    p_in = ft.TextField(hint_text="Пароль", password=True, border_radius=12, filled=True, bgcolor=CARD)
    tg_in = ft.TextField(hint_text="Telegram ID (необязательно)", border_radius=12, filled=True, bgcolor=CARD, visible=False)
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

    def auth(e):
        u, p = u_in.value.strip().lower(), p_in.value.strip()
        if not u or not p:
            a_err.value = "Введите логин и пароль"
            page.update()
            return
        ep = "register" if st["reg"] else "login"
        r = requests.post(API + S + ep, json={"login": u, "password": p, "tg_id": tg_in.value.strip()}, timeout=10).json()
        if r.get("ok"):
            st["user"] = r["login"]
            u_lbl.value = f"Кабинет: {st['user']}"
            auth_box.visible, main_box.visible = False, True
            load()
        else:
            a_err.value = r.get("error", "Ошибка")
            page.update()

    auth_box = ft.Container(visible=False, padding=24, content=ft.Column([
        ft.Icon(ft.Icons.ACCOUNT_CIRCLE_ROUNDED, size=70, color=P1), a_title, u_in, p_in, tg_in, a_err,
        ft.Container(bgcolor=P1, border_radius=12, height=48, alignment=ft.alignment.center, on_click=auth, content=a_btn_t),
        ft.Container(content=sw_t, on_click=toggle, padding=8)
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12))

    u_lbl = ft.Text("Кабинет", size=12, color="#E0E0E0")
    dot = ft.Icon(ft.Icons.CIRCLE, size=10, color="#00E676")
    lbl = ft.Text("Онлайн", size=12, color="white")
    hdr = ft.Container(gradient=ft.LinearGradient(colors=[P2, P1]), padding=20, content=ft.Row([
        ft.Column([ft.Text("WB.Track [by.Жекич]", size=19, weight="bold", color="white"), u_lbl], expand=True),
        ft.Row([dot, lbl], spacing=4),
        ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color="white", on_click=lambda e: load())
    ]))

    sku_in = ft.TextField(hint_text="Артикул WB", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD)
    pr_in = ft.TextField(hint_text="Цена до (₽)", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, expand=True)
    lim_in = ft.TextField(value="1", prefix_text="Шт: ", keyboard_type=ft.KeyboardType.NUMBER, border_radius=12, filled=True, bgcolor=CARD, width=130)
    col = ft.Column(spacing=10)

    def render():
        col.controls.clear()
        for it in st["tasks"]:
            img = ft.Image(src=it.get("image", ""), width=60, height=80, fit=ft.ImageFit.COVER)
            p_s = f"Сейчас: {it.get('current_sbp')} ₽ (СБП) | {it.get('current_wallet')} ₽ (Кош.)" if it.get("current_sbp") else "Загрузка цены..."
            info = ft.Column([
                ft.Text(it.get("name") or f"Товар {it['sku']}", weight="bold", size=14, color="white", max_lines=2),
                ft.Text(p_s, size=12, color="#00E676"),
                ft.Text(f"Цель: до {it['target_price']} ₽ ({it['bought']}/{it['limit']})", size=12, color="#B0B0C0")
            ], expand=True, spacing=2)
            del_b = ft.IconButton(icon=ft.Icons.DELETE_ROUNDED, icon_color="#FF5252", on_click=lambda _, s=it["sku"]: delete(s))
            col.controls.append(ft.Container(bgcolor=CARD, padding=10, border_radius=14, content=ft.Row([img, info, del_b])))

    def load():
        r = requests.get(API + S + "tasks", params={"user": st["user"]}, timeout=10)
        if r.status_code == 200:
            st["tasks"] = r.json()
            dot.color, lbl.value = "#00E676", "Онлайн"
            render()
        else:
            dot.color, lbl.value = "#FF5252", "Офлайн"
        page.update()

    def add(e):
        if sku_in.value and pr_in.value:
            requests.post(API + S + "tasks", json={"owner": st["user"], "sku": int(sku_in.value.strip()), "target_price": int(pr_in.value.strip()), "limit": int(lim_in.value.strip() or 1)}, timeout=10)
            sku_in.value, pr_in.value = "", ""
            load()

    def delete(sku):
        requests.delete(API + S + "tasks" + S + str(sku), params={"user": st["user"]}, timeout=10)
        load()

    add_b = ft.Container(bgcolor=P1, border_radius=12, height=48, alignment=ft.alignment.center, on_click=add, content=ft.Text("Добавить в отслеживание", color="white", weight="bold"))
    main_box = ft.Column([hdr, ft.Container(padding=16, content=ft.Column([sku_in, ft.Row([pr_in, lim_in]), add_b, col], spacing=12))], visible=False)
    page.add(splash, auth_box, main_box)

    def go():
        splash.visible, auth_box.visible = False, True
        page.update()

    threading.Timer(1.5, go).start()

ft.app(target=main)

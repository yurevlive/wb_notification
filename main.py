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

    state = {"mode": "all", "tasks": []}

    splash = ft.Container(
        height=620, bgcolor=BG_COLOR, alignment=ft.alignment.center,
        content=ft.Column([
            ft.Container(width=84, height=84, border_radius=24, gradient=ft.LinearGradient(colors=[WB_PURPLE, "#7C3AED"]), alignment=ft.alignment.center, content=ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=46, color="white")),
            ft.Text("WB.Track", size=38, weight="bold", color="white"),
            ft.Text("[by.Жекич]", size=18, weight="w500", color="#E040FB")
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)
    )

    dot = ft.Icon(ft.Icons.CIRCLE, size=10, color="#00E676")
    lbl = ft.Text("Онлайн", size=12, color="white", weight="w500")
    badge = ft.Container(content=ft.Row([dot, lbl], spacing=5), bgcolor="#2A1B3D", padding=ft.padding.symmetric(horizontal=10, vertical=5), border_radius=20)

    header = ft.Container(
        gradient=ft.LinearGradient(colors=[WB_DARK, WB_PURPLE]),
        padding=ft.padding.only(left=20, right=15, top=35, bottom=20),
        border_radius=ft.border_radius.only(bottom_left=24, bottom_right=24),
        content=ft.Row([
            ft.Column([ft.Text("WB.Track [by.Жекич]", size=21, weight="bold", color="white"), ft.Text("Общий доступ 24/7", size=12, color="#E0E0E0")], expand=True, spacing=2),
            badge,
            ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color="white", bgcolor="#33FFFFFF", on_click=lambda e: load_list())
        ])
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
            tasks_col.controls.append(ft.Container(bgcolor=CARD_COLOR, padding=25, border_radius=16, alignment=ft.alignment.center, content=ft.Text("Список пуст", color="#888899")))
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
            tasks_col.controls.append(ft.Container(bgcolor=CARD_COLOR, padding=12, border_radius=16, border=ft.border.all(1, "#2A2A35"), content=ft.Row([thumb, info, del_b], spacing=10)))

    def load_list():
        status_txt.value = ""
        try:
            state["tasks"] = requests.get(API_URL + S + "tasks", timeout=8).json()
            dot.color, lbl.value = "#00E676", "Онлайн"
            render()
        except Exception as err:
            dot.color, lbl.value = "#FF5252", "Офлайн"
            status_txt.value, status_txt.color = f"⚠️ Нет связи: {err}", "#FF5252"
        page.update()

    def add_item(e):
        if not sku_in.value or not price_in.value:
            status_txt.value, status_txt.color = "⚠️ Заполните поля!", "#FFB74D"
            page.update()
            return
        status_txt.value, status_txt.color = "⏳ Загружаю фото и цену...", "#E040FB"
        page.update()
        try:
            requests.post(API_URL + S + "tasks", json={"sku": int(sku_in.value.strip()), "target_price": int(price_in.value.strip()), "limit": int(limit_in.value.strip() or 1)}, timeout=10)
            sku_in.value, price_in.value, limit_in.value = "", "", "1"
            load_list()
        except Exception as err:
            status_txt.value, status_txt.color = f"⚠️ Ошибка: {err}", "#FF5252"
            page.update()

    def del_item(sku):
        requests.delete(API_URL + S + "tasks" + S + str(sku), timeout=8)
        load_list()

    add_btn = ft.Container(gradient=ft.LinearGradient(colors=[WB_PURPLE, "#9C27B0"]), border_radius=14, height=50, alignment=ft.alignment.center, ink=True, on_click=add_item, content=ft.Row([ft.Icon(ft.Icons.ADD_SHOPPING_CART_ROUNDED, color="white", size=20), ft.Text("Добавить в отслеживание", color="white", weight="bold", size=15)], alignment=ft.MainAxisAlignment.CENTER, spacing=8))
    body = ft.Container(padding=18, content=ft.Column([sku_in, ft.Row([price_in, limit_in], spacing=10), add_btn, status_txt, ft.Divider(height=10, color="#2A2A35"), ft.Row([b_all, b_act, b_done], spacing=8, scroll="auto"), tasks_col], spacing=14))
    main_view = ft.Column([header, body], visible=False, spacing=0)
    page.add(splash, main_view)

    def start():
        splash.visible, main_view.visible = False, True
        load_list()

    threading.Timer(1.8, start).start()

ft.app(target=main)

import threading
import flet as ft
import requests

HOST = "127.0.0." + "1:8000"
API_URL = f"http://{HOST}"

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

    current_filter = {"mode": "all"}
    cached_tasks = []

    # Заставка при запуске
    splash_screen = ft.Container(
        height=620,
        bgcolor=BG_COLOR,
        alignment=ft.alignment.center,
        content=ft.Column([
            ft.Container(
                width=84,
                height=84,
                border_radius=24,
                gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=[WB_PURPLE, "#7C3AED"]),
                alignment=ft.alignment.center,
                content=ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=46, color="white")
            ),
            ft.Container(height=12),
            ft.Text("WB.Track", size=38, weight="bold", color="white"),
            ft.Text("[by.Жекич]", size=18, weight="w500", color="#E040FB")
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
    )

    # Шапка
    badge_dot = ft.Icon(ft.Icons.CIRCLE, size=10, color="#00E676")
    badge_label = ft.Text("Онлайн", size=12, color="white", weight="w500")
    server_badge = ft.Container(content=ft.Row([badge_dot, badge_label], spacing=5), bgcolor="#2A1B3D", padding=ft.padding.symmetric(horizontal=10, vertical=5), border_radius=20)

    header = ft.Container(
        gradient=ft.LinearGradient(begin=ft.alignment.top_left, end=ft.alignment.bottom_right, colors=[WB_DARK, WB_PURPLE]),
        padding=ft.padding.only(left=20, right=15, top=35, bottom=20),
        border_radius=ft.border_radius.only(bottom_left=24, bottom_right=24),
        content=ft.Row([
            ft.Column([
                ft.Text("WB.Track [by.Жекич]", size=21, weight="bold", color="white"),
                ft.Text("Автомониторинг и выкуп", size=12, color="#E0E0E0")
            ], expand=True, spacing=2),
            server_badge,
            ft.IconButton(icon=ft.Icons.REFRESH_ROUNDED, icon_color="white", bgcolor="#33FFFFFF", on_click=lambda e: load_list())
        ])
    )

    # Поля ввода
    sku_input = ft.TextField(hint_text="Артикул товара WB", prefix_icon=ft.Icons.QR_CODE_2_ROUNDED, keyboard_type=ft.KeyboardType.NUMBER, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE, content_padding=ft.padding.symmetric(horizontal=14, vertical=16))
    price_input = ft.TextField(hint_text="Желаемая цена до (₽)", prefix_icon=ft.Icons.CURRENCY_RUBLE_ROUNDED, keyboard_type=ft.KeyboardType.NUMBER, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE, content_padding=ft.padding.symmetric(horizontal=14, vertical=16), expand=True)
    limit_input = ft.TextField(value="1", prefix_text="Шт: ", prefix_icon=ft.Icons.SHOPPING_BAG_OUTLINED, keyboard_type=ft.KeyboardType.NUMBER, border_radius=14, filled=True, bgcolor=CARD_COLOR, border_color="transparent", focused_border_color=WB_PURPLE, content_padding=ft.padding.symmetric(horizontal=12, vertical=16), width=155)

    status_text = ft.Text("", size=13, weight="w500")
    tasks_column = ft.Column(spacing=12)

    # Вкладки фильтрации
    tab_all_text = ft.Text("Все (0)", size=13, weight="bold", color="white")
    tab_active_text = ft.Text("Активные (0)", size=13, weight="w500", color="#A0A0B0")
    tab_done_text = ft.Text("Выкупленные (0)", size=13, weight="w500", color="#A0A0B0")

    tab_all_btn = ft.Container(content=tab_all_text, bgcolor=WB_PURPLE, padding=ft.padding.symmetric(horizontal=14, vertical=8), border_radius=20, on_click=lambda e: set_filter("all"))
    tab_active_btn = ft.Container(content=tab_active_text, bgcolor=CARD_COLOR, padding=ft.padding.symmetric(horizontal=14, vertical=8), border_radius=20, on_click=lambda e: set_filter("active"))
    tab_done_btn = ft.Container(content=tab_done_text, bgcolor=CARD_COLOR, padding=ft.padding.symmetric(horizontal=14, vertical=8), border_radius=20, on_click=lambda e: set_filter("done"))

    filter_row = ft.Row([tab_all_btn, tab_active_btn, tab_done_btn], spacing=8, scroll="auto")

    def set_filter(mode: str):
        current_filter["mode"] = mode
        tab_all_btn.bgcolor = WB_PURPLE if mode == "all" else CARD_COLOR
        tab_all_text.color = "white" if mode == "all" else "#A0A0B0"
        tab_all_text.weight = "bold" if mode == "all" else "w500"

        tab_active_btn.bgcolor = WB_PURPLE if mode == "active" else CARD_COLOR
        tab_active_text.color = "white" if mode == "active" else "#A0A0B0"
        tab_active_text.weight = "bold" if mode == "active" else "w500"

        tab_done_btn.bgcolor = WB_PURPLE if mode == "done" else CARD_COLOR
        tab_done_text.color = "white" if mode == "done" else "#A0A0B0"
        tab_done_text.weight = "bold" if mode == "done" else "w500"

        render_tasks()
        page.update()

    def update_badge(online: bool):
        badge_dot.color = "#00E676" if online else "#FF5252"
        badge_label.value = "Онлайн" if online else "Офлайн"

    def render_tasks():
        tasks_column.controls.clear()
        active_items = [t for t in cached_tasks if t["bought"] < t["limit"]]
        done_items = [t for t in cached_tasks if t["bought"] >= t["limit"]]

        tab_all_text.value = f"Все ({len(cached_tasks)})"
        tab_active_text.value = f"Активные ({len(active_items)})"
        tab_done_text.value = f"Выкупленные ({len(done_items)})"

        mode = current_filter["mode"]
        visible_items = active_items if mode == "active" else (done_items if mode == "done" else cached_tasks)

        if not visible_items:
            empty_box = ft.Container(bgcolor=CARD_COLOR, padding=25, border_radius=16, alignment=ft.alignment.center, content=ft.Column([ft.Icon(ft.Icons.INBOX_ROUNDED, size=40, color="#666677"), ft.Text("В этой вкладке пока пусто", color="#888899", size=14)], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8))
            tasks_column.controls.append(empty_box)
            return

        for item in visible_items:
            is_done = item["bought"] >= item["limit"]
            badge_bg = "#1B3B2B" if is_done else "#2D1B3D"
            badge_color = "#00E676" if is_done else "#E040FB"
            badge_text = "✅ Выкуплено" if is_done else "⏳ Поиск цены"

            product_name = item.get("name") or f"Товар {item['sku']}"
            image_url = item.get("image") or ""
            cur_sbp = item.get("current_sbp")
            cur_wallet = item.get("current_wallet")

            prices_line = f"Сейчас: {cur_sbp} ₽ (СБП) • {cur_wallet} ₽ (Кош.)" if (cur_sbp and cur_wallet) else "Сейчас: загрузка цены..."
            goal_line = f"Цель: до {item['target_price']} ₽ • Куплено: {item['bought']} из {item['limit']}"

            img_widget = ft.Image(src=image_url, width=68, height=88, fit=ft.ImageFit.COVER, error_content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, color="#666677")) if image_url else ft.Icon(ft.Icons.SHOPPING_BAG_OUTLINED, color="#666677")
            thumb = ft.Container(width=68, height=88, border_radius=12, bgcolor="#2A2A35", clip_behavior=ft.ClipBehavior.HARD_EDGE, content=img_widget)

            title_txt = ft.Text(product_name, weight="bold", size=14, color="white", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
            status_chip = ft.Container(content=ft.Text(badge_text, size=10, color=badge_color, weight="bold"), bgcolor=badge_bg, padding=ft.padding.symmetric(horizontal=7, vertical=2), border_radius=6)
            meta_row = ft.Row([ft.Text(f"Арт: {item['sku']}", size=11, color="#8E8E9E"), status_chip], spacing=6)
            price_txt = ft.Text(prices_line, size=12, color="#00E676", weight="w500")
            goal_txt = ft.Text(goal_line, size=12, color="#B0B0C0")
            del_btn = ft.IconButton(icon=ft.Icons.DELETE_ROUNDED, icon_color="#FF5252", bgcolor="#26FF5252", on_click=lambda _, s=item["sku"]: delete_item(s))

            card = ft.Container(bgcolor=CARD_COLOR, padding=12, border_radius=16, border=ft.border.all(1, "#2A2A35"), content=ft.Row([thumb, ft.Column([title_txt, meta_row, price_txt, goal_txt], expand=True, spacing=4), del_btn], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER))
            tasks_column.controls.append(card)

    def load_list(e=None):
        nonlocal cached_tasks
        status_text.value = ""
        try:
            cached_tasks = requests.get(f"{API_URL}/tasks", timeout=4).json()
            update_badge(True)
            render_tasks()
        except Exception as err:
            update_badge(False)
            status_text.value = f"⚠️ Нет связи с Termux: {err}"
            status_text.color = "#FF5252"
        page.update()

    def add_item(e):
        if not sku_input.value or not price_input.value:
            status_text.value = "⚠️ Укажите артикул и желаемую цену!"
            status_text.color = "#FFB74D"
            page.update()
            return
        status_text.value = "⏳ Загружаю фото и цены товара..."
        status_text.color = "#E040FB"
        page.update()
        try:
            data = {"sku": int(sku_input.value.strip()), "target_price": int(price_input.value.strip()), "limit": int(limit_input.value.strip() or 1)}
            requests.post(f"{API_URL}/tasks", json=data, timeout=8)
            sku_input.value = ""
            price_input.value = ""
            limit_input.value = "1"
            load_list()
        except Exception as err:
            status_text.value = f"⚠️ Ошибка добавления: {err}"
            status_text.color = "#FF5252"
            page.update()

    def delete_item(sku):
        try:

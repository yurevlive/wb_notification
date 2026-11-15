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

    # ==========================================
    # ЗАСТАВКА ПРИ ЗАПУСКЕ
    # ==========================================
    splash_screen = ft.Container(
        height=620,
        bgcolor=BG_COLOR,
        alignment=ft.alignment.center,
        content=ft.Column([
            ft.Container(
                width=84,
                height=84,
                border_radius=24,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=[WB_PURPLE, "#7C3AED"]
                ),
                alignment=ft.alignment.center,
                content=ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=46, color="white")
            ),
            ft.Container(height=12),
            ft.Text(
                "WB.Track",
                size=38,
                weight="bold",
                color="white",
                text_align=ft.TextAlign.CENTER
            ),
            ft.Text(
                "[by.Жекич]",
                size=18,
                weight="w500",
                color="#E040FB",
                text_align=ft.TextAlign.CENTER
            )
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4)
    )

    # ==========================================
    # ШАПКА ПРИЛОЖЕНИЯ
    # ==========================================
    badge_dot = ft.Icon(ft.Icons.CIRCLE, size=10, color="#00E676")
    badge_label = ft.Text("Онлайн", size=12, color="white", weight="w500")

    server_badge = ft.Container(
        content=ft.Row([badge_dot, badge_label], spacing=5),
        bgcolor="#2A1B3D",
        padding=ft.padding.symmetric(horizontal=10, vertical=5),
        border_radius=20
    )

    header = ft.Container(
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[WB_DARK, WB_PURPLE],
        ),
        padding=ft.padding.only(left=20, right=15, top=35, bottom=20),
        border_radius=ft.border_radius.only(bottom_left=24, bottom_right=24),
        content=ft.Row([
            ft.Column([
                ft.Text("WB.Track [by.Жекич]", size=21, weight="bold", color="white"),
                ft.Text("Автомониторинг и выкуп", size=12, color="#E0E0E0")
            ], expand=True, spacing=2),
            server_badge,
            ft.IconButton(
                icon=ft.Icons.REFRESH_ROUNDED,
                icon_color="white",
                bgcolor="#33FFFFFF",
                on_click=lambda e: load_list()
            )
        ])
    )

    # ==========================================
    # ФОРМА ДОБАВЛЕНИЯ ТОВАРА
    # ==========================================
    sku_input = ft.TextField(
        hint_text="Артикул товара WB (например, 596432419)",
        prefix_icon=ft.Icons.QR_CODE_2_ROUNDED,
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=14,
        filled=True,
        bgcolor=CARD_COLOR,
        border_color="transparent",
        focused_border_color=WB_PURPLE,
        content_padding=ft.padding.symmetric(horizontal=14, vertical=16)
    )

    price_input = ft.TextField(
        hint_text="Желаемая цена до (₽)",
        prefix_icon=ft.Icons.CURRENCY_RUBLE_ROUNDED,
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=14,
        filled=True,
        bgcolor=CARD_COLOR,
        border_color="transparent",
        focused_border_color=WB_PURPLE,
        content_padding=ft.padding.symmetric(horizontal=14, vertical=16),
        expand=True
    )

    limit_input = ft.TextField(
        value="1",
        prefix_text="Шт: ",
        prefix_icon=ft.Icons.SHOPPING_BAG_OUTLINED,
        keyboard_type=ft.KeyboardType.NUMBER,
        border_radius=14,
        filled=True,
        bgcolor=CARD_COLOR,
        border_color="transparent",
        focused_border_color=WB_PURPLE,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=16),
        width=155
    )

    status_text = ft.Text("", size=13, weight="w500")
    tasks_column = ft.Column(spacing=12)

    # ==========================================
    # ВКЛАДКИ ФИЛЬТРАЦИИ
    # ==========================================
    tab_all_text = ft.Text("Все (0)", size=13, weight="bold", color="white")
    tab_active_text = ft.Text("Активные (0)", size=13, weight="w500", color="#A0A0B0")
    tab_done_text = ft.Text("Выкупленные (0)", size=13, weight="w500", color="#A0A0B0")

    tab_all_btn = ft.Container(
        content=tab_all_text,
        bgcolor=WB_PURPLE,
        padding=ft.padding.symmetric(horizontal=14, vertical=8),
        border_radius=20,
        on_click=lambda e: set_filter("all")
    )
    tab_active_btn = ft.Container(
        content=tab_active_text,
        bgcolor=CARD_COLOR,
        padding=ft.padding.symmetric(horizontal=14, vertical=8),
        border_radius=20,
        on_click=lambda e: set_filter("active")
    )
    tab_done_btn = ft.Container(
        content=tab_done_text,
        bgcolor=CARD_COLOR,
        padding=ft.padding.symmetric(horizontal=14, vertical=8),
        border_radius=20,
        on_click=lambda e: set_filter("done")
    )

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
        if online:
            badge_dot.color = "#00E676"
            badge_label.value = "Онлайн"
        else:
            badge_dot.color = "#FF5252"
            badge_label.value = "Офлайн"

    def render_tasks():
        tasks_column.controls.clear()
        total_count = len(cached_tasks)
        active_items = [t for t in cached_tasks if t["bought"] < t["limit"]]
        done_items = [t for t in cached_tasks if t["bought"] >= t["limit"]]

        tab_all_text.value = f"Все ({total_count})"
        tab_active_text.value = f"Активные ({len(active_items)})"
        tab_done_text.value = f"Выкупленные ({len(done_items)})"

        mode = current_filter["mode"]
        if mode == "active":
            visible_items = active_items
        elif mode == "done":
            visible_items = done_items
        else:
            visible_items = cached_tasks

        if not visible_items:
            tasks_column.controls.append(
                ft.Container(
                    bgcolor=CARD_COLOR,
                    padding=25,
                    border_radius=16,
                    alignment=ft.alignment.center,
                    content=ft.Column([
                        ft.Icon(ft.Icons.INBOX_ROUNDED, size=40, color="#666677"),
                        ft.Text("В этой вкладке пока пусто", color="#888899", size=14)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
                )
            )
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

            if cur_sbp is not None and cur_wallet is not None:
                prices_line = f"Сейчас: {cur_sbp} ₽ (СБП)  •  {cur_wallet} ₽ (Кошелек)"
            else:
                prices_line = "Сейчас: загрузка цены..."

            thumb = ft.Container(
                width=68,
                height=88,
                border_radius=12,
                bgcolor="#2A2A35",
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
                content=ft.Image(
                    src=image_url,
                    width=68,
                    height=88,
                    fit=ft.ImageFit.COVER,
                    error_content=ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED_OUTLINED, color="#666677")
                ) if image_url else ft.Icon(ft.Icons.SHOPPING_BAG_OUTLINED, color="#666677")
            )

            tasks_column.controls.append(
                ft.Container(
                    bgcolor=CARD_COLOR,
                    padding=12,
                    border_radius=16,
                    border=ft.border.all(1, "#2A2A35"),
                    content=ft.Row([
                        thumb,
                        ft.Column([
                            ft.Text(
                                product_name,
                                weight="bold",
                                size=14,
                                color="white",
                                max_lines=2,

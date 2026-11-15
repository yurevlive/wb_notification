import time
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

    # ==========================================
    # АНИМИРОВАННАЯ ЗАСТАВКА ПРИ ЗАПУСКЕ
    # ==========================================
    splash_content = ft.Container(
        opacity=0,
        scale=0.85,
        animate_opacity=ft.animation.Animation(700, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.animation.Animation(700, ft.AnimationCurve.EASE_OUT_BACK),
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

    splash_screen = ft.Container(
        expand=True,
        bgcolor=BG_COLOR,
        alignment=ft.alignment.center,
        content=splash_content
    )

    # ==========================================
    # ОСНОВНОЙ ИНТЕРФЕЙС ПРИЛОЖЕНИЯ
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
    tasks_counter = ft.Text("Активные задачи (0)", size=17, weight="bold", color="white")

    def update_badge(online: bool):
        if online:
            badge_dot.color = "#00E676"
            badge_label.value = "Онлайн"
        else:
            badge_dot.color = "#FF5252"
            badge_label.value = "Офлайн"

    def load_list(e=None):
        tasks_column.controls.clear()
        status_text.value = ""
        try:
            res = requests.get(f"{API_URL}/tasks", timeout=3).json()
            update_badge(True)
            tasks_counter.value = f"Активные задачи ({len(res)})"

            if not res:
                tasks_column.controls.append(
                    ft.Container(
                        bgcolor=CARD_COLOR,
                        padding=25,
                        border_radius=16,
                        alignment=ft.alignment.center,
                        content=ft.Column([
                            ft.Icon(ft.Icons.INBOX_ROUNDED, size=40, color="#666677"),
                            ft.Text("Список отслеживания пуст", color="#888899", size=14)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)
                    )
                )

            for item in res:
                is_done = item["bought"] >= item["limit"]
                badge_bg = "#1B3B2B" if is_done else "#2D1B3D"
                badge_color = "#00E676" if is_done else "#E040FB"
                badge_text = "✅ Выкуплено" if is_done else "⏳ В поиске цены"

                tasks_column.controls.append(
                    ft.Container(
                        bgcolor=CARD_COLOR,
                        padding=15,
                        border_radius=16,
                        border=ft.border.all(1, "#2A2A35"),
                        content=ft.Row([
                            ft.Column([
                                ft.Row([
                                    ft.Text(f"Арт: {item['sku']}", weight="bold", size=16, color="white"),
                                    ft.Container(
                                        content=ft.Text(badge_text, size=11, color=badge_color, weight="bold"),
                                        bgcolor=badge_bg,
                                        padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                        border_radius=8
                                    )
                                ], spacing=8),
                                ft.Text(
                                    f"Цель: до {item['target_price']} ₽  •  Куплено: {item['bought']} из {item['limit']}",
                                    size=13,
                                    color="#B0B0C0"
                                )
                            ], expand=True, spacing=6),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_ROUNDED,
                                icon_color="#FF5252",
                                bgcolor="#26FF5252",
                                tooltip="Удалить задачу",
                                on_click=lambda _, s=item["sku"]: delete_item(s)
                            )
                        ])
                    )
                )
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
        try:
            data = {
                "sku": int(sku_input.value.strip()),
                "target_price": int(price_input.value.strip()),
                "limit": int(limit_input.value.strip() or 1)
            }
            requests.post(f"{API_URL}/tasks", json=data, timeout=3)
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
            requests.delete(f"{API_URL}/tasks/{sku}", timeout=3)
            load_list()
        except Exception:
            pass

    add_button = ft.Container(
        gradient=ft.LinearGradient(colors=[WB_PURPLE, "#9C27B0"]),
        border_radius=14,
        height=50,
        alignment=ft.alignment.center,
        ink=True,
        on_click=add_item,
        content=ft.Row([
            ft.Icon(ft.Icons.ADD_SHOPPING_CART_ROUNDED, color="white", size=20),
            ft.Text("Добавить в отслеживание", color="white", weight="bold", size=15)
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=8)
    )

    body = ft.Container(
        padding=18,
        content=ft.Column([
            sku_input,
            ft.Row([price_input, limit_input], spacing=10),
            add_button,
            status_text,
            ft.Divider(height=15, color="#2A2A35"),
            tasks_counter,
            tasks_column
        ], spacing=14)
    )


import flet as ft
import requests

HOST = "127.0.0." + "1:8000"
API_URL = f"http://{HOST}"

def main(page: ft.Page):
    page.title = "WB Автозаказ"
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 15
    page.scroll = "adaptive"

    sku_input = ft.TextField(label="Артикул WB", keyboard_type=ft.KeyboardType.NUMBER)
    price_input = ft.TextField(label="Желаемая цена до (₽)", keyboard_type=ft.KeyboardType.NUMBER)
    limit_input = ft.TextField(label="Лимит покупок (шт.)", value="1", keyboard_type=ft.KeyboardType.NUMBER)
    status_text = ft.Text("", size=14)
    tasks_column = ft.Column(spacing=10)

    def load_list(e=None):
        tasks_column.controls.clear()
        status_text.value = ""
        try:
            res = requests.get(f"{API_URL}/tasks", timeout=3).json()
            if not res:
                tasks_column.controls.append(ft.Text("Список отслеживания пуст.", italic=True))
            for item in res:
                is_done = item["bought"] >= item["limit"]
                status_badge = "✅ Выкуплено" if is_done else "⏳ Отслеживается"
                tasks_column.controls.append(
                    ft.Card(
                        content=ft.Container(
                            padding=12,
                            content=ft.Row([
                                ft.Column([
                                    ft.Text(f"Артикул: {item['sku']}", weight="bold", size=16),
                                    ft.Text(f"Цель: до {item['target_price']} ₽ | Куплено: {item['bought']} из {item['limit']}"),
                                    ft.Text(status_badge, size=12, color="green" if is_done else "blue")
                                ], expand=True),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_color="red",
                                    on_click=lambda _, s=item["sku"]: delete_item(s)
                                )
                            ])
                        )
                    )
                )
        except Exception as err:
            status_text.value = f"⚠️ Ошибка связи с Termux: {err}"
            status_text.color = "red"
        page.update()

    def add_item(e):
        if not sku_input.value or not price_input.value:
            status_text.value = "Заполните артикул и желаемую цену!"
            status_text.color = "orange"
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
            status_text.color = "red"
            page.update()

    def delete_item(sku):
        try:
            requests.delete(f"{API_URL}/tasks/{sku}", timeout=3)
            load_list()
        except Exception:
            pass

    page.add(
        ft.Row([
            ft.Text("WB Автозаказ", size=22, weight="bold", expand=True),
            ft.IconButton(icon=ft.Icons.REFRESH, on_click=load_list)
        ]),
        sku_input,
        price_input,
        limit_input,
        ft.ElevatedButton("Добавить в отслеживание", on_click=add_item, width=400, height=45),
        status_text,
        ft.Divider(),
        ft.Text("Активные задачи:", size=18, weight="bold"),
        tasks_column
    )
    load_list()

ft.app(target=main)

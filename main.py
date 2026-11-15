import time
import threading
import flet as ft
import flet_webview as fwv
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

    wb_site = "https://www.wildberries" + ".ru"
    webview = fwv.WebView(
        url=f"{wb_site}/lk/basket",
        expand=True,
        height=420,
        visible=False
    )

    def toggle_wb_browser(e=None):
        webview.visible = not webview.visible
        if webview.visible:
            webview.url = f"{wb_site}/lk/basket"
        page.update()

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

    def auto_buyer_loop():
        while True:
            try:
                r = requests.get(f"{API_URL}/pending_buy", timeout=3).json()
                sku = r.get("sku")
                if sku:
                    status_text.value = f"🔥 Цена упала! Открываю корзину для автовыкупа {sku}..."
                    status_text.color = "green"
                    webview.visible = True
                    webview.url = f"{wb_site}/catalog/{sku}/detail.aspx"
                    page.update()
                    time.sleep(6)

                    js_add = """
                    setTimeout(() => {
                        let btns = Array.from(document.querySelectorAll('button'));
                        let buyBtn = btns.find(b => b.innerText.includes('корзину') || b.innerText.includes('Купить'));
                        if (buyBtn) buyBtn.click();
                    }, 1000);
                    """
                    webview.run_javascript(js_add)
                    time.sleep(4)

                    webview.url = f"{wb_site}/lk/basket"
                    page.update()
                    time.sleep(6)

                    js_order = """
                    setTimeout(() => {
                        let btns = Array.from(document.querySelectorAll('button'));
                        let orderBtn = btns.find(b => b.innerText.includes('Заказать'));
                        if (orderBtn && !orderBtn.disabled) orderBtn.click();
                    }, 1500);
                    """
                    webview.run_javascript(js_order)
                    time.sleep(5)

                    requests.post(f"{API_URL}/confirm_buy/{sku}", timeout=3)
                    load_list()
            except Exception:
                pass
            time.sleep(5)

    threading.Thread(target=auto_buyer_loop, daemon=True).start()

    page.add(
        ft.Row([
            ft.Text("WB Автозаказ", size=22, weight="bold", expand=True),
            ft.ElevatedButton("Браузер WB", on_click=toggle_wb_browser),
            ft.IconButton(icon=ft.Icons.REFRESH, on_click=load_list)
        ]),
        webview,
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

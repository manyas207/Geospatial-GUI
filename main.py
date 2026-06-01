# main.py

import tkinter as tk

from dashboard.input import InputPage
from dashboard.analysis import AnalysisPage
from dashboard.dashboard_page import DashboardPage

root = tk.Tk()

root.title("Geospatial Dashboard")
root.geometry("1000x700")

sidebar = tk.Frame(root, width=250, bg="lightgray")
sidebar.pack(side="left", fill="y")

main_area = tk.Frame(root)
main_area.pack(side="right", fill="both", expand=True)

pages = {
    "inputs": InputPage(main_area),
    "analysis": AnalysisPage(main_area),
    "dashboard": DashboardPage(main_area)
}

def show_page(page_name):

    for page in pages.values():
        page.pack_forget()

    pages[page_name].pack(
        fill="both",
        expand=True
    )


tk.Button(
    sidebar,
    text="Inputs",
    command=lambda: show_page("inputs")
).pack(fill="x")

tk.Button(
    sidebar,
    text="Preprocessing",
    command=lambda: show_page("preprocessing")
).pack(fill="x")

tk.Button(
    sidebar,
    text="Analysis",
    command=lambda: show_page("analysis")
).pack(fill="x")

tk.Button(
    sidebar,
    text="Dashboard",
    command=lambda: show_page("dashboard")
).pack(fill="x")

show_page("inputs")

root.mainloop()
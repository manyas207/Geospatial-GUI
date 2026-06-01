# frontend/dashboard_page.py

import tkinter as tk

class DashboardPage(tk.Frame):

    def __init__(self, parent):
        super().__init__(parent)

        tk.Label(
            self,
            text="Results Dashboard"
        ).pack()

        self.results_text = tk.Text(
            self,
            height=20,
            width=60
        )

        self.results_text.pack()
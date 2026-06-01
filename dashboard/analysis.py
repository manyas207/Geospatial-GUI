# frontend/analysis_page.py

import tkinter as tk

class AnalysisPage(tk.Frame):

    def __init__(self, parent):
        super().__init__(parent)

        tk.Label(
            self,
            text="Analysis Options"
        ).pack()

        tk.Button(
            self,
            text="Pixel-Based"
        ).pack()

        tk.Button(
            self,
            text="Object-Based"
        ).pack()

        tk.Button(
            self,
            text="Deep Learning"
        ).pack()
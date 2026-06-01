# frontend/input_page.py

import tkinter as tk
from tkinter import filedialog

class InputPage(tk.Frame):

    def __init__(self, parent):
        super().__init__(parent)

        tk.Label(self, text="Dataset").pack()

        self.dataset_var = tk.StringVar(value="Landsat")

        tk.OptionMenu(
            self,
            self.dataset_var,
            "Landsat",
            "Sentinel",
            "HLS"
        ).pack()

        tk.Label(self, text="Year").pack()

        self.year_entry = tk.Entry(self)
        self.year_entry.pack()

        tk.Button(
            self,
            text="Upload Raster",
            command=self.upload_file
        ).pack()

        self.clip_var = tk.BooleanVar()
        self.cloud_var = tk.BooleanVar()
        self.ndvi_var = tk.BooleanVar()

        tk.Checkbutton(
            self,
            text="Clip Image",
            variable=self.clip_var
        ).pack()

        tk.Checkbutton(
            self,
            text="Cloud Mask",
            variable=self.cloud_var
        ).pack()

        tk.Checkbutton(
            self,
            text="Generate NDVI",
            variable=self.ndvi_var
        ).pack()

    def upload_file(self):
        filepath = filedialog.askopenfilename()
        print(filepath)
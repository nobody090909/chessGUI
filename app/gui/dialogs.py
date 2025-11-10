from __future__ import annotations
import tkinter as tk
from tkinter import simpledialog, filedialog

def ask_fen(parent: tk.Tk) -> str | None:
    return simpledialog.askstring("Load FEN", "FEN string:", parent=parent)

def save_pgn_dialog(parent: tk.Tk) -> str | None:
    return filedialog.asksaveasfilename(parent=parent, defaultextension=".pgn", filetypes=[("PGN files","*.pgn")])

def open_pgn_dialog(parent: tk.Tk) -> str | None:
    return filedialog.askopenfilename(parent=parent, filetypes=[("PGN files","*.pgn"), ("All files","*.*")])

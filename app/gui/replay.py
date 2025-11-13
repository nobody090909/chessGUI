from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import List
from history import MoveHistory

class ReplayPanel(ttk.Frame):
    """이동 리스트 + ⏮⏪⏩⏭ 컨트롤, 더블클릭으로 점프"""
    def __init__(self, master, board, history: MoveHistory, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.board = board
        self.history = history

        bar = ttk.Frame(self); bar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        ttk.Button(bar, text="<<", width=3, command=lambda: self.history.first(self.board)).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="<", width=3, command=lambda: self.history.prev(self.board)).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text=">", width=3, command=lambda: self.history.next(self.board)).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text=">>", width=3, command=lambda: self.history.last(self.board)).pack(side=tk.LEFT, padx=2)
        self.lbl = ttk.Label(bar, text="0 / 0"); self.lbl.pack(side=tk.RIGHT)

        self.listbox = tk.Listbox(self, height=18, activestyle="dotbox")
        self.listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=(0,4))
        self.listbox.bind("<Double-Button-1>", self._on_dblclick)

        self.history.bind_on_change(self._on_history_change)
        self._refresh()

    def _on_dblclick(self, _):
        sel = self.listbox.curselection()
        if not sel: return
        target = sel[0] * 2 + 2
        target = max(0, min(self.history.total, target))
        self.history.goto(self.board, target)

    def _refresh(self):
        self.listbox.delete(0, tk.END)
        rows: List[str] = []
        moves = self.history.moves()
        i, num = 0, 1
        while i < len(moves):
            left = moves[i].san
            right = moves[i+1].san if i + 1 < len(moves) else ""
            rows.append(f"{num}. {left}  {right}".rstrip())
            num += 1; i += 2
        for r in rows: self.listbox.insert(tk.END, r)
        cur = self.history.cursor
        row_idx = max(0, (cur - 1) // 2) if cur > 0 else 0
        if self.listbox.size():
            self.listbox.selection_clear(0, tk.END)
            self.listbox.activate(row_idx)
            self.listbox.selection_set(row_idx)
        self.lbl.config(text=f"{self.history.cursor} / {self.history.total}")

    def _on_history_change(self, *_): self._refresh()

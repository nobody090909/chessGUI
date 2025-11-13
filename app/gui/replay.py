from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from history import MoveHistory

class ReplayPanel(ttk.Frame):
    """
    - Move list UI with jump controls
    - Double-click to jump
    - redraw: callable to re-render board
    - on_jump: callable after a jump (e.g., trigger AI turn)
    - busy: callable(bool) to show/hide a lightweight busy indicator
    """
    def __init__(
        self,
        master,
        board,
        history: MoveHistory,
        *,
        redraw: Optional[Callable[[], None]] = None,
        on_jump: Optional[Callable[[], None]] = None,
        busy: Optional[Callable[[bool], None]] = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.board = board
        self.history = history
        self._redraw = redraw or (lambda: None)
        self._on_jump = on_jump or (lambda: None)
        self._busy = busy or (lambda _on: None)

        # toolbar
        bar = ttk.Frame(self)
        bar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)
        self.btn_first = ttk.Button(bar, text="<<", width=3, command=self._goto_first)
        self.btn_prev  = ttk.Button(bar, text="<", width=3, command=self._goto_prev)
        self.btn_next  = ttk.Button(bar, text=">", width=3, command=self._goto_next)
        self.btn_last  = ttk.Button(bar, text=">>", width=3, command=self._goto_last)
        self.btn_first.pack(side=tk.LEFT, padx=2)
        self.btn_prev.pack(side=tk.LEFT, padx=2)
        self.btn_next.pack(side=tk.LEFT, padx=2)
        self.btn_last.pack(side=tk.LEFT, padx=2)
        self.lbl_status = ttk.Label(bar, text="0 / 0")
        self.lbl_status.pack(side=tk.RIGHT)

        # move list
        self.listbox = tk.Listbox(self, height=18, activestyle="dotbox")
        self.listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.listbox.bind("<Double-Button-1>", self._on_dblclick)

        # history change binding
        self.history.bind_on_change(self._on_history_change)
        self._refresh_list()

    # external rebind when board object is replaced
    def rebind(self, new_board) -> None:
        self.board = new_board
        self._refresh_list()

    # buttons
    def _goto_first(self):
        self._busy(True)
        try:
            self.history.first(self.board)
            self._redraw()
            self._on_jump()
        finally:
            self._busy(False)

    def _goto_last(self):
        self._busy(True)
        try:
            self.history.last(self.board)
            self._redraw()
            self._on_jump()
        finally:
            self._busy(False)

    def _goto_prev(self):
        self._busy(True)
        try:
            self.history.prev(self.board)
            self._redraw()
            self._on_jump()
        finally:
            self._busy(False)

    def _goto_next(self):
        self._busy(True)
        try:
            self.history.next(self.board)
            self._redraw()
            self._on_jump()
        finally:
            self._busy(False)

    # double-click jump (row → ply = row*2+2)
    def _on_dblclick(self, ev):
        row = self.listbox.nearest(ev.y)
        target = min(self.history.total, row * 2 + 2)
        self._busy(True)
        try:
            self.history.goto(self.board, target)
            self._redraw()
            self._on_jump()
        finally:
            self._busy(False)

    # UI refresh on history changes
    def _on_history_change(self, cursor: int, total: int):
        self._refresh_list()
        self._redraw()

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        rows: List[str] = []
        moves = self.history.moves()

        i = 0
        move_no = 1
        while i < len(moves):
            left = moves[i].san
            right = moves[i + 1].san if i + 1 < len(moves) else ""
            rows.append(f"{move_no}. {left}  {right}".rstrip())
            move_no += 1
            i += 2

        for r in rows:
            self.listbox.insert(tk.END, r)

        current = self.history.cursor
        row_idx = max(0, (current - 1) // 2) if current > 0 else 0
        if self.listbox.size() > 0:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.activate(row_idx)
            self.listbox.selection_set(row_idx)

        self.lbl_status.config(text=f"{self.history.cursor} / {self.history.total}")

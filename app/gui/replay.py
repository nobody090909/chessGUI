from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional

from app.history import MoveHistory


class ReplayPanel(ttk.Frame):
    """
    - MoveHistory + board를 받아 이동 리스트/점프 컨트롤 제공
    - 버튼/더블클릭으로 임의 ply로 점프
    - redraw: 보드 재렌더 콜백
    - on_jump: 점프 후 호출(예: AI 한 턴 트리거)
    - busy: (on: bool) -> None  형태의 로딩 표시 콜백
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

        # 상단 컨트롤 바
        bar = ttk.Frame(self)
        bar.pack(side=tk.TOP, fill=tk.X, padx=4, pady=4)

        self.btn_first = ttk.Button(bar, text="<<", width=3, command=self._goto_first)
        self.btn_prev  = ttk.Button(bar, text="<", width=3, command=self._goto_prev)
        self.btn_next  = ttk.Button(bar, text=">>", width=3, command=self._goto_next)
        self.btn_last  = ttk.Button(bar, text=">", width=3, command=self._goto_last)

        self.btn_first.pack(side=tk.LEFT, padx=2)
        self.btn_prev.pack(side=tk.LEFT, padx=2)
        self.btn_next.pack(side=tk.LEFT, padx=2)
        self.btn_last.pack(side=tk.LEFT, padx=2)

        self.lbl_status = ttk.Label(bar, text="0 / 0")
        self.lbl_status.pack(side=tk.RIGHT)

        # 이동 리스트(1수=최대 2 ply를 한 줄로 표기)
        self.listbox = tk.Listbox(self, height=18, activestyle="dotbox")
        self.listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))
        self.listbox.bind("<Double-Button-1>", self._on_dblclick)

        # 히스토리 변경 시 UI/보드 리프레시
        self.history.bind_on_change(self._on_history_change)
        self._refresh_list()

    # 외부에서 보드가 교체되면 반드시 호출
    def rebind(self, new_board) -> None:
        self.board = new_board
        # 리스트와 상태 갱신
        self._refresh_list()

    # ---------- 버튼 핸들러 ----------
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

    # ---------- 더블클릭 ----------
    def _on_dblclick(self, ev):
        row = self.listbox.nearest(ev.y)
        target = min(self.history.total, row * 2 + 2)  # 해당 수의 끝으로 점프
        self._busy(True)
        try:
            self.history.goto(self.board, target)
            self._redraw()
            self._on_jump()
        finally:
            self._busy(False)

    # ---------- 히스토리 변경 시 UI 갱신 ----------
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

        # 커서가 가리키는 ply를 행 단위로 강조
        current = self.history.cursor
        row_idx = max(0, (current - 1) // 2) if current > 0 else 0
        if self.listbox.size() > 0:
            self.listbox.selection_clear(0, tk.END)
            self.listbox.activate(row_idx)
            self.listbox.selection_set(row_idx)

        self.lbl_status.config(text=f"{self.history.cursor} / {self.history.total}")

from __future__ import annotations
import tkinter as tk
import chess
from typing import Optional, Set, Callable

from engine.rules import GameState
from gui.assets_loader import Assets

LIGHT_COLOR = "#EEEED2"
DARK_COLOR  = "#769656"
HL_MOVE_FROM = "#F6F669"
HL_MOVE_TO   = "#BACA2B"
HL_LEGAL     = "#f1e57a"


class BoardView(tk.Canvas):
    def __init__(self, master: tk.Misc, game: GameState, assets: Assets,
                 *, padding: int = 20, sq_size: int = 72, flipped: bool = False,
                 on_user_move: Optional[Callable[[str], None]] = None):
        width = height = padding*2 + sq_size*8
        super().__init__(master, width=width, height=height, bg="white", highlightthickness=0)
        self.game = game
        self.assets = assets
        self.padding = padding
        self.sq_size = sq_size
        self.flipped = flipped
        self.on_user_move = on_user_move

        self.selected_sq: Optional[int] = None
        self.legal_targets: Set[int] = set()

        # Drag state
        self.drag_from_sq: Optional[int] = None
        self.drag_img_id: Optional[int] = None
        self.drag_code: Optional[str] = None

        # Animation state
        self.animating: bool = False
        self.anim_from_sq: Optional[int] = None
        self.anim_to_sq: Optional[int] = None
        self.anim_img_id: Optional[int] = None
        self.anim_code: Optional[str] = None

        # Input bindings
        self.bind("<Button-1>", self._on_click)          # click-click
        self.bind("<ButtonPress-1>", self._on_press)     # drag start
        self.bind("<B1-Motion>", self._on_motion)        # dragging
        self.bind("<ButtonRelease-1>", self._on_release) # drop

        self.redraw()

    # ---- Draw ----
    def redraw(self):
        self.delete("all")
        self._draw_board()
        self._draw_highlights()
        self._draw_pieces()
        # animation overlay는 별도로 관리(필요 시 재생성)

    def _draw_board(self):
        for r in range(8):
            for f in range(8):
                color = LIGHT_COLOR if (r+f) % 2 == 0 else DARK_COLOR
                sq = self._fr_to_square(f, r)
                x, y = self._sq_to_xy(sq)
                self.create_rectangle(x, y, x+self.sq_size, y+self.sq_size, fill=color, outline=color)

    def _draw_highlights(self):
        last = self.game.last_move
        if last:
            for sq, clr in [(last.from_square, HL_MOVE_FROM), (last.to_square, HL_MOVE_TO)]:
                x, y = self._sq_to_xy(sq)
                self.create_rectangle(x, y, x+self.sq_size, y+self.sq_size, outline=clr, width=3)

        if self.selected_sq is not None:
            x, y = self._sq_to_xy(self.selected_sq)
            self.create_rectangle(x, y, x+self.sq_size, y+self.sq_size, outline="#e0c53b", width=3)
            for tgt in self.legal_targets:
                tx, ty = self._sq_to_xy(tgt)
                self.create_oval(tx+self.sq_size*0.4, ty+self.sq_size*0.4,
                                 tx+self.sq_size*0.6, ty+self.sq_size*0.6,
                                 fill=HL_LEGAL, outline="")

    def _draw_pieces(self):
        pm = self.game.piece_map()
        for sq, piece in pm.items():
            # Hide squares involved in drag/animation
            if self.drag_from_sq is not None and sq == self.drag_from_sq:
                continue
            if self.animating and (sq == self.anim_from_sq or sq == self.anim_to_sq):
                continue
            code = ("w" if piece.color == chess.WHITE else "b") + piece.symbol().upper()
            x, y = self._sq_to_xy(sq)
            self.create_image(x, y, image=self.assets.img(code), anchor="nw")

    # ---- Mapping ----
    def _sq_to_xy(self, sq: int):
        f = chess.square_file(sq)
        r = chess.square_rank(sq)
        if self.flipped:
            f = 7 - f
            r = 7 - r
        x = self.padding + f*self.sq_size
        y = self.padding + (7-r)*self.sq_size
        return x, y

    def _xy_to_square(self, x: int, y: int):
        if x < self.padding or y < self.padding:
            return None
        f = (x - self.padding) // self.sq_size
        r_from_top = (y - self.padding) // self.sq_size
        if f < 0 or f >= 8 or r_from_top < 0 or r_from_top >= 8:
            return None
        rank_idx = 7 - r_from_top
        file_idx = f
        if self.flipped:
            file_idx = 7 - file_idx
            rank_idx = 7 - rank_idx
        return chess.square(file_idx, rank_idx)

    def _fr_to_square(self, file_idx, rank_idx):
        if self.flipped:
            file_idx = 7 - file_idx
            rank_idx = 7 - rank_idx
        return chess.square(file_idx, rank_idx)

    # ---- Click→Click ----
    def _on_click(self, event):
        if self.animating or self.game.is_game_over():
            return
        sq = self._xy_to_square(event.x, event.y)
        if sq is None:
            return
        piece = self.game.board.piece_at(sq)

        # 선택 토글: 같은 칸 다시 클릭하면 해제만 하고 종료
        if self.selected_sq is not None and sq == self.selected_sq:
            self.selected_sq = None
            self.legal_targets.clear()
            self.redraw()
            return

        if self.selected_sq is None:
            if piece is None or piece.color != self.game.board.turn:
                return
            self.selected_sq = sq
            self.legal_targets = self.game.legal_moves_from(sq)
            self.redraw()
        else:
            # 다른 칸 클릭 → 이동 시도
            mv = chess.Move(self.selected_sq, sq)
            uci = mv.uci()
            if mv not in self.game.board.legal_moves:
                if (chess.square_rank(self.selected_sq) in (6,1) and chess.square_rank(sq) in (7,0)):
                    uci = chess.Move(self.selected_sq, sq, promotion=chess.QUEEN).uci()
            if self.on_user_move and self.selected_sq != sq:
                self.on_user_move(uci)
            # selection reset
            self.selected_sq = None
            self.legal_targets.clear()
            self.redraw()

    # ---- Drag & Drop ----
    def _on_press(self, event):
        if self.animating or self.game.is_game_over():
            return
        sq = self._xy_to_square(event.x, event.y)
        if sq is None:
            return
        piece = self.game.board.piece_at(sq)
        if piece is None or piece.color != self.game.board.turn:
            return

        self.drag_from_sq = sq
        self.drag_code = ("w" if piece.color == chess.WHITE else "b") + piece.symbol().upper()

        # 드래그 시작 시 마커 유지
        self.selected_sq = sq
        self.legal_targets = self.game.legal_moves_from(sq)

        # 먼저 원본을 숨기고
        self.redraw()
        # 오버레이 생성
        img = self.assets.img(self.drag_code)
        self.drag_img_id = self.create_image(event.x - img.width()//2,
                                             event.y - img.height()//2,
                                             image=img, anchor="nw")

    def _on_motion(self, event):
        if self.drag_img_id is None:
            return
        img = self.assets.img(self.drag_code) if self.drag_code else None
        if img:
            self.coords(self.drag_img_id, event.x - img.width()//2, event.y - img.height()//2)

    def _on_release(self, event):
        if self.drag_from_sq is None:
            return

        # 오버레이 제거
        if self.drag_img_id is not None:
            try:
                self.delete(self.drag_img_id)
            except Exception:
                pass
        self.drag_img_id = None

        to_sq = self._xy_to_square(event.x, event.y)
        from_sq = self.drag_from_sq

        # drag state 해제는 항상 선행(예외/리턴에도 안전)
        self.drag_from_sq = None
        self.drag_code = None

        # 드롭이 보드 밖이거나 같은 칸이면 → 이동 취소(선택 유지/토글)
        if to_sq is None:
            self.selected_sq = None
            self.legal_targets.clear()
            self.redraw()
            return

        if to_sq == from_sq:
            # 같은 칸 드롭: 선택만 유지(토글하려면 한 번 더 클릭)
            self.selected_sq = from_sq
            self.legal_targets = self.game.legal_moves_from(from_sq)
            self.redraw()
            return

        mv = chess.Move(from_sq, to_sq)
        uci = mv.uci()
        if mv not in self.game.board.legal_moves:
            if (chess.square_rank(from_sq) in (6,1) and chess.square_rank(to_sq) in (7,0)):
                uci = chess.Move(from_sq, to_sq, promotion=chess.QUEEN).uci()

        if self.on_user_move:
            self.on_user_move(uci)

        self.selected_sq = None
        self.legal_targets.clear()
        self.redraw()

    # ---- Animation ----
    def animate_move(self, piece_code: str, from_sq: int, to_sq: int,
                     duration_ms: int = 180, done: Optional[Callable[[], None]] = None):
        if self.animating:
            return
        self.animating = True
        self.anim_from_sq = from_sq
        self.anim_to_sq = to_sq
        self.anim_code = piece_code

        start_x, start_y = self._sq_to_xy(from_sq)
        end_x, end_y = self._sq_to_xy(to_sq)
        img = self.assets.img(piece_code)

        self.redraw()
        self.anim_img_id = self.create_image(start_x, start_y, image=img, anchor="nw")

        steps = max(int(duration_ms / 16), 8)
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps

        def step(i=0):
            if self.anim_img_id is None:
                return
            self.move(self.anim_img_id, dx, dy)
            if i + 1 < steps:
                self.after(16, step, i+1)
            else:
                self.coords(self.anim_img_id, end_x, end_y)
                try:
                    self.delete(self.anim_img_id)
                except Exception:
                    pass
                self.anim_img_id = None
                self.animating = False
                self.anim_from_sq = None
                self.anim_to_sq = None
                self.anim_code = None
                if done:
                    done()

        self.after(16, step)

    # ---- Helpers ----
    def set_flipped(self, flipped: bool):
        self.flipped = flipped
        self.redraw()

    def set_bottom(self, color: str):
        """color ∈ {"white","black"} — ensure that color is at the bottom."""
        self.flipped = (color.lower() == "black")
        self.redraw()

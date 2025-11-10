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

        self.bind("<Button-1>", self._on_click)
        self.redraw()

    # --- Drawing ---
    def redraw(self):
        self.delete("all")
        self._draw_board()
        self._draw_highlights()
        self._draw_pieces()

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
                self.create_oval(tx+self.sq_size*0.4, ty+self.sq_size*0.4, tx+self.sq_size*0.6, ty+self.sq_size*0.6,
                                 fill=HL_LEGAL, outline="")

    def _draw_pieces(self):
        pm = self.game.piece_map()
        for sq, piece in pm.items():
            code = ("w" if piece.color == chess.WHITE else "b") + piece.symbol().upper()
            x, y = self._sq_to_xy(sq)
            self.create_image(x, y, image=self.assets.img(code), anchor="nw")  # keep reference in assets

    # --- Mapping ---
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

    # --- Events ---
    def _on_click(self, event):
        if self.game.is_game_over():
            return
        sq = self._xy_to_square(event.x, event.y)
        if sq is None:
            return
        piece = self.game.board.piece_at(sq)
        if self.selected_sq is None:
            if piece is None or piece.color != self.game.board.turn:
                return
            self.selected_sq = sq
            self.legal_targets = self.game.legal_moves_from(sq)
            self.redraw()
        else:
            mv = chess.Move(self.selected_sq, sq)
            uci = mv.uci()
            # promote to queen auto if needed
            if mv not in self.game.board.legal_moves:
                if (chess.square_rank(self.selected_sq) in (6,1)
                    and chess.square_rank(sq) in (7,0)):
                    uci = chess.Move(self.selected_sq, sq, promotion=chess.QUEEN).uci()
            if self.on_user_move:
                self.on_user_move(uci)
            self.selected_sq = None
            self.legal_targets.clear()
            self.redraw()

    # --- Public helpers ---
    def set_flipped(self, flipped: bool):
        self.flipped = flipped
        self.redraw()

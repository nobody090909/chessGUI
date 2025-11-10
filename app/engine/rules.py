from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Set
import chess
import chess.pgn
from io import StringIO

@dataclass
class MoveInfo:
    uci: str
    san: str

class GameState:
    """Thin wrapper around python-chess Board, for GUI friendliness."""
    def __init__(self, fen: Optional[str] = None):
        self.board = chess.Board(fen) if fen else chess.Board()
        self._last_move = None

    # ----- Queries -----
    @property
    def fen(self) -> str:
        return self.board.fen()

    @property
    def turn_name(self) -> str:
        return "White" if self.board.turn else "Black"

    @property
    def last_move(self) -> Optional[chess.Move]:
        return self._last_move

    def piece_map(self):
        return self.board.piece_map()

    def legal_moves_from(self, sq: int) -> Set[int]:
        return {m.to_square for m in self.board.legal_moves if m.from_square == sq}

    def is_game_over(self) -> bool:
        return self.board.is_game_over()

    def status_text(self) -> str:
        if self.board.is_game_over():
            if self.board.is_checkmate():
                # side to move has no legal move; winner is opposite
                winner = "White" if not self.board.turn else "Black"
                return f"Checkmate. {winner} wins."
            if self.board.is_stalemate():
                return "Draw (stalemate)."
            if self.board.is_insufficient_material():
                return "Draw (insufficient material)."
            return "Draw."
        extra = " (check)" if self.board.is_check() else ""
        return f"Turn: {self.turn_name}{extra}"

    # ----- Mutations -----
    def apply_uci(self, uci: str) -> bool:
        try:
            mv = chess.Move.from_uci(uci)
        except Exception:
            return False
        if mv not in self.board.legal_moves:
            # auto-queen promotion attempt
            try:
                if mv.promotion is None:
                    promo = chess.Move(mv.from_square, mv.to_square, chess.QUEEN)
                    if promo in self.board.legal_moves:
                        mv = promo
            except Exception:
                pass
        if mv in self.board.legal_moves:
            self.board.push(mv)
            self._last_move = mv
            return True
        return False

    def apply_move(self, move: chess.Move) -> bool:
        if move in self.board.legal_moves:
            self.board.push(move)
            self._last_move = move
            return True
        return False

    def undo(self, steps: int = 1) -> None:
        for _ in range(min(steps, len(self.board.move_stack))):
            self.board.pop()
        self._last_move = self.board.peek() if self.board.move_stack else None

    # ----- PGN -----
    def export_pgn(self) -> str:
        game = chess.pgn.Game()
        game.setup(self.board.starting_fen)
        node = game
        for mv in self.board.move_stack:
            node = node.add_variation(mv)
        sio = StringIO()
        print(game, file=sio, end="")
        return sio.getvalue()

    def load_fen(self, fen: str) -> None:
        self.board = chess.Board(fen)
        self._last_move = None

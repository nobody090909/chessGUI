from __future__ import annotations
import queue, threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import chess

from engine.rules import GameState
from engine.simple_ai import SimpleAI
from gui.board_view import BoardView
from gui.assets_loader import load_piece_images
from gui.dialogs import ask_fen, save_pgn_dialog
from services.telemetry import setup_logging
from replay_bootstrap import attach_replay

DEFAULT_SQ = 72

class ChessApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Check, Mate")
        self.resizable(False, False)

        self.project_root = Path(__file__).resolve().parents[2]
        self.logger = setup_logging(self.project_root)

        self.sq_size = DEFAULT_SQ
        self.assets = load_piece_images(self.project_root, self.sq_size)

        self.game = GameState()
        self.ai_color: str | None = None
        self.ai_worker: threading.Thread | None = None
        self.ai_queue: queue.Queue = queue.Queue()
        self.player_bottom: str = "white"

        self._build_menu()
        self.status_var = tk.StringVar(value=self.game.status_text())
        self.board_view = BoardView(self, self.game, self.assets, sq_size=self.sq_size,
                                    on_user_move=self._on_user_move)
        self.board_view.set_bottom(self.player_bottom)
        self.board_view.pack()
        self.status_bar = tk.Label(self, textvariable=self.status_var, anchor="w", padx=8)
        self.status_bar.pack(fill="x")

        self.after(80, self._poll_ai)

        try:
            attach_replay(self)
        except Exception as e:
            print(f"[x] replay attach failed: {e}")

    def _build_menu(self):
        menubar = tk.Menu(self)
        game = tk.Menu(menubar, tearoff=0)
        game.add_command(label="New Game", command=self._new_game)
        game.add_command(label="Undo (Takeback)", command=self._undo_move)
        game.add_separator()
        game.add_command(label="Load FEN", command=self._load_fen)
        game.add_command(label="Save PGN", command=self._save_pgn)
        game.add_separator()
        game.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="Game", menu=game)

        view = tk.Menu(menubar, tearoff=0)
        view.add_command(label="Flip Board", command=self._flip_board)
        view.add_command(label="Bottom: White", command=lambda: self._set_bottom("white"))
        view.add_command(label="Bottom: Black", command=lambda: self._set_bottom("black"))
        menubar.add_cascade(label="View", menu=view)

        mode = tk.Menu(menubar, tearoff=0)
        mode.add_command(label="Human vs Human", command=lambda: self._set_mode(None))
        mode.add_command(label="Play as White vs AI", command=lambda: self._set_mode("black", player_bottom="white"))
        mode.add_command(label="Play as Black vs AI", command=lambda: self._set_mode("white", player_bottom="black"))
        menubar.add_cascade(label="Mode", menu=mode)
        self.config(menu=menubar)

    # ---- Actions ----
    def _on_user_move(self, uci: str):
        # 같은 칸(e7e7) 입력 사전 차단
        if len(uci) >= 4 and uci[:2] == uci[2:4]:
            return
        mv = chess.Move.from_uci(uci)
        piece = self.game.board.piece_at(mv.from_square)
        if not piece:
            return
        code = ('w' if piece.color == chess.WHITE else 'b') + piece.symbol().upper()

        def commit():
            ok = self.game.apply_uci(uci)
            if ok:
                self.status_var.set(self.game.status_text())
                self.board_view.redraw()
                self._maybe_start_ai()
            else:
                messagebox.showwarning("Illegal", f"Illegal move: {uci}")
                self.board_view.redraw()

        self.board_view.animate_move(code, mv.from_square, mv.to_square, duration_ms=180, done=commit)

    def _new_game(self):
        self._cancel_ai()
        self.game = GameState()
        self.board_view.game = self.game
        self.board_view.set_bottom(self.player_bottom)
        self.status_var.set(self.game.status_text())
        self.board_view.redraw()
        self._maybe_start_ai()

    def _undo_move(self):
        self._cancel_ai()
        if not self.game.board.move_stack:
            return
        self.game.undo(1)
        if self.ai_color is not None and self.game.board.move_stack and \
           (("white" if self.game.board.turn == chess.WHITE else "black") == self.ai_color):
            self.game.undo(1)
        self.status_var.set(self.game.status_text())
        self.board_view.redraw()
        self._maybe_start_ai()

    def _load_fen(self):
        fen = ask_fen(self)
        if not fen:
            return
        try:
            self._cancel_ai()
            self.game.load_fen(fen)
            self.status_var.set(self.game.status_text())
            self.board_view.redraw()
            self._maybe_start_ai()
        except Exception as e:
            messagebox.showerror("FEN Error", str(e))

    def _save_pgn(self):
        path = save_pgn_dialog(self)
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.game.export_pgn())
        messagebox.showinfo("Saved", f"Saved PGN to {path}")

    def _flip_board(self):
        self.board_view.set_flipped(not self.board_view.flipped)

    def _set_bottom(self, color: str):
        self.player_bottom = color
        self.board_view.set_bottom(color)

    def _set_mode(self, ai_color: str | None, player_bottom: str | None = None):
        self.ai_color = ai_color
        if player_bottom:
            self._set_bottom(player_bottom)
        self.status_var.set(self.game.status_text())
        self._maybe_start_ai()

    # ---- AI control (local simple_ai) ----
    def _cancel_ai(self):
        self.ai_worker = None  # simple thread, no cancel hook

    def _maybe_start_ai(self):
        if self.game.is_game_over() or self.ai_color is None:
            if self.game.is_game_over():
                messagebox.showinfo("Game Over", self.game.status_text())
            return
        side = "white" if self.game.board.turn == chess.WHITE else "black"
        if side != self.ai_color:
            return

        def run_ai():
            try:
                mv = SimpleAI().best_move(self.game.board, depth=3)
                if mv:
                    self.ai_queue.put(("move", {"move": mv.uci()}))
                else:
                    self.ai_queue.put(("error", {"error": "no_move"}))
            except Exception as e:
                self.ai_queue.put(("error", {"error": "exception", "detail": str(e)}))

        t = threading.Thread(target=run_ai, daemon=True)
        self.ai_worker = t
        t.start()

    def _poll_ai(self):
        try:
            while True:
                kind, payload = self.ai_queue.get_nowait()
                if kind == "move":
                    uci = payload.get("move")
                    mv = chess.Move.from_uci(uci)
                    piece = self.game.board.piece_at(mv.from_square)
                    if not piece:
                        if uci and self.game.apply_uci(uci):
                            self.board_view.redraw()
                            self.status_var.set(self.game.status_text())
                        continue
                    code = ('w' if piece.color == chess.WHITE else 'b') + piece.symbol().upper()

                    def commit_ai():
                        if uci and self.game.apply_uci(uci):
                            self.board_view.redraw()
                            self.status_var.set(self.game.status_text())
                            if self.game.is_game_over():
                                messagebox.showinfo("Game Over", self.game.status_text())
                        else:
                            messagebox.showwarning("AI Move Illegal", f"Illegal move: {uci}")

                    self.board_view.animate_move(code, mv.from_square, mv.to_square, duration_ms=180, done=commit_ai)

                elif kind == "error":
                    detail = payload.get("detail", "")
                    msg = payload.get("error", "error")
                    messagebox.showerror("AI Error", f"{msg}\n{detail}")
        except queue.Empty:
            pass
        finally:
            self.after(80, self._poll_ai)

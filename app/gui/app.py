from __future__ import annotations
import json
import queue
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import chess

from engine.simple_ai import SimpleAI
from engine.rules import GameState
from engine.remote_ai import RemoteAIClient, RemoteAIWorker
from gui.board_view import BoardView
from gui.assets_loader import load_piece_images
from gui.dialogs import ask_fen, save_pgn_dialog
from services.telemetry import setup_logging

DEFAULT_SQ = 72

class ChessApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Chess — Remote AI")
        self.resizable(False, False)

        self.project_root = Path(__file__).resolve().parents[2]
        self.logger = setup_logging(self.project_root)

        # Config
        self.configs = self._load_config()
        self.sq_size = DEFAULT_SQ
        self.assets = load_piece_images(self.project_root, self.sq_size)

        # Game & AI
        self.game = GameState()
        self.ai_color: str | None = None   # None | "white" | "black"
        self.ai_client: RemoteAIClient | None = None
        self.ai_worker: RemoteAIWorker | None = None
        self.ai_queue: queue.Queue = queue.Queue()
        self.ai_think_ms = int(self.configs.get("THINK_MS", 2000))

        if (url := self.configs.get("AI_URL")):
            self.ai_client = RemoteAIClient(base_url=url, api_key=self.configs.get("API_KEY"),
                                            timeout=float(self.configs.get("TIMEOUT", 15)))

        # UI
        self._build_menu()
        self.status_var = tk.StringVar(value=self.game.status_text())
        self.board_view = BoardView(self, self.game, self.assets, sq_size=self.sq_size,
                                    on_user_move=self._on_user_move)
        self.board_view.pack()
        self.status_bar = tk.Label(self, textvariable=self.status_var, anchor="w", padx=8)
        self.status_bar.pack(fill="x")

        # Polling
        self.after(80, self._poll_ai)

    # ----- Config -----
    def _load_config(self) -> dict:
        cfg_path = self.project_root / "configs" / "config.json"
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            return data
        except FileNotFoundError:
            messagebox.showwarning("Config", f"Config not found: {cfg_path}\n원격 AI 없이 실행됩니다.")
            return {}
        except Exception as e:
            messagebox.showerror("Config Error", str(e))
            return {}

    # ----- Menu/UI -----
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
        menubar.add_cascade(label="View", menu=view)

        mode = tk.Menu(menubar, tearoff=0)
        mode.add_command(label="Human vs Human", command=lambda: self._set_mode(None))
        mode.add_command(label="Human (White) vs AI", command=lambda: self._set_mode("black"))
        mode.add_command(label="Human (Black) vs AI", command=lambda: self._set_mode("white"))
        menubar.add_cascade(label="Mode", menu=mode)

        self.config(menu=menubar)

    # ----- Callbacks -----
    def _on_user_move(self, uci: str):
        applied = self.game.apply_uci(uci)
        if not applied:
            return
        self.status_var.set(self.game.status_text())
        self.board_view.redraw()
        self._maybe_start_ai()

    # ----- Actions -----
    def _new_game(self):
        self._cancel_ai()
        self.game = GameState()
        self.board_view.game = self.game
        self.status_var.set(self.game.status_text())
        self.board_view.redraw()
        self._maybe_start_ai()

    def _undo_move(self):
        self._cancel_ai()
        if not self.game.board.move_stack:
            return
        self.game.undo(1)
        if self.ai_color is not None and self.game.board.move_stack and (("white" if self.game.board.turn else "black") == self.ai_color):
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

    def _set_mode(self, ai_color: str | None):
        self.ai_color = ai_color
        self.status_var.set(self.game.status_text())
        self._maybe_start_ai()

    # ----- AI control -----
    def _cancel_ai(self):
        if self.ai_worker and self.ai_worker.is_alive():
            self.ai_worker.cancel()
        self.ai_worker = None

    def _maybe_start_ai(self):
        if self.game.is_game_over() or self.ai_color is None:
            if self.game.is_game_over():
                messagebox.showinfo("Game Over", self.game.status_text())
            return
        
        side = "white" if self.game.board.turn == chess.WHITE else "black"
        if side != self.ai_color:
            return
        if not self.ai_client:
            # messagebox.showwarning("AI", "원격 AI가 설정되지 않았습니다 (configs/config.json).")
            mv = SimpleAI().best_move(self.game.board, depth=3)
            if mv:
                self.game.apply_uci(mv.uci())
                self.board_view.redraw()
                self.status_var.set(self.game.status_text())
                if self.game.is_game_over():
                    messagebox.showinfo("Game Over", self.game.status_text())
            return
        
        fen = self.game.fen
        history = [mv.uci() for mv in self.game.board.move_stack]
        self.ai_worker = RemoteAIWorker(self.ai_client, fen, history, self.ai_queue, think_ms=self.ai_think_ms)
        self.ai_worker.start()

    def _poll_ai(self):
        try:
            while True:
                kind, payload = self.ai_queue.get_nowait()
                if kind == "move":
                    uci = payload.get("move")
                    if uci:
                        ok = self.game.apply_uci(uci)
                        if ok:
                            self.board_view.redraw()
                            self.status_var.set(self.game.status_text())
                            if self.game.is_game_over():
                                messagebox.showinfo("Game Over", self.game.status_text())
                        else:
                            messagebox.showwarning("AI Move Illegal", f"Illegal move from AI: {uci}")
                elif kind == "error":
                    detail = payload.get("detail")
                    msg = payload.get("error", "error")
                    messagebox.showerror("AI Error", f"{msg}\n{detail or ''}")
        except Exception:
            pass
        finally:
            self.after(80, self._poll_ai)

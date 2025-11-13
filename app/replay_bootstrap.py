from __future__ import annotations

import copy
import tkinter as tk
from typing import Any, Callable, Optional, Tuple

from history import MoveHistory, MoveMeta
from gui.replay import ReplayPanel

# ----------------------------
#  Resolve Board & Game
# ----------------------------
def _resolve_board_and_game(app: Any) -> Tuple[Any, Optional[Any]]:
    """
    Priority: game.board → board → state.board/ctx.board
    """
    game = getattr(app, "game", None)
    if game is not None and hasattr(game, "board"):
        return game.board, game
    if hasattr(app, "board"):
        return getattr(app, "board"), game
    for attr0 in ("state", "ctx"):
        if hasattr(app, attr0):
            obj0 = getattr(app, attr0)
            if hasattr(obj0, "board"):
                return getattr(obj0, "board"), game
    raise RuntimeError("Board object not found.")

# ----------------------------
#  Adapters (snapshot / restore / reapply)
# ----------------------------
def _make_adapters(board: Any) -> Tuple[
    Callable[[Any], Any], Callable[[Any, Any], None], Callable[[Any, MoveMeta], None],
]:
    # Prefer python-chess FEN
    if hasattr(board, "fen") and callable(getattr(board, "fen")) and hasattr(board, "set_fen"):
        def get_state(b): return {"fen": b.fen()}
        def set_state(b, st): b.set_fen(st["fen"])
    elif hasattr(board, "to_fen") and hasattr(board, "from_fen"):
        def get_state(b): return {"fen": b.to_fen()}
        def set_state(b, st): b.from_fen(st["fen"])
    elif hasattr(board, "to_dict") and hasattr(board, "from_dict"):
        def get_state(b): return copy.deepcopy(b.to_dict())
        def set_state(b, st): b.from_dict(copy.deepcopy(st))
    else:
        def get_state(b): return copy.deepcopy(b.__dict__)
        def set_state(b, st): b.__dict__.update(copy.deepcopy(st))

    def apply_move(b, m: MoveMeta):
        # 1) SAN 우선: python-chess는 push_san 사용
        if m.san and hasattr(b, "push_san"):
            b.push_san(m.san); return
        # 2) UCI 경로: from/to 존재하면 push
        if hasattr(b, "push") and m.from_sq and m.to_sq:
            try:
                import chess  # type: ignore
                uci = m.from_sq + m.to_sq + (m.promotion.lower() if m.promotion else "")
                mv = chess.Move.from_uci(uci)
                b.push(mv); return
            except Exception:
                pass
        # 3) 커스텀 (from,to,promotion)
        for name in ("apply_move_algebraic", "make_move", "move", "apply_move"):
            fn = getattr(b, name, None)
            if fn:
                fn(m.from_sq, m.to_sq, promotion=m.promotion); return
        raise RuntimeError("apply_move: no suitable method on board for replay")

    return get_state, set_state, apply_move

# ----------------------------
#  Helpers: redraw/AI/busy
# ----------------------------
def _find_redraw(app: Any) -> Callable[[], None]:
    # Prefer BoardView.redraw()
    bv = getattr(app, "board_view", None)
    if bv is not None and hasattr(bv, "redraw") and callable(bv.redraw):
        return bv.redraw
    for n in ("redraw_board", "draw_board", "render_board", "refresh", "redraw", "update_board", "repaint"):
        fn = getattr(app, n, None)
        if callable(fn): return fn
    return lambda: None

def _find_ai_tick(app: Any, game: Optional[Any]) -> Callable[[], None]:
    # ChessApp has _maybe_start_ai()
    for owner in (app, game):
        if owner is None: continue
        for n in ("_maybe_start_ai", "maybe_ai_turn", "ai_move_if_needed", "ai_play", "engine_move", "play_ai_turn", "ai_step"):
            fn = getattr(owner, n, None)
            if callable(fn):
                return fn
    return lambda: None

def _make_busy(app: Any) -> Callable[[bool], None]:
    def busy(on: bool) -> None:
        try:
            app.config(cursor="watch" if on else "")
            app.update_idletasks(); app.update()
        except Exception:
            pass
    return busy

# ----------------------------
#  Sentinel to avoid double-wrapping
# ----------------------------
def _mark_wrapped(owner: Any, name: str) -> bool:
    tag = "__replay_wrapped__"
    s = getattr(owner, tag, None)
    if s is None:
        s = set(); setattr(owner, tag, s)
    if name in s:
        return True
    s.add(name); return False

# ----------------------------
#  Record only committed moves (Board side)
# ----------------------------
def _wrap_commit_methods_on_board(board: Any, history: MoveHistory) -> None:
    candidates = (
        ("apply_move_algebraic", "alg"),
        ("make_move", "alg"),
        ("move", "alg"),
        ("apply_move", "alg"),
        ("apply_san", "san"),
        ("push_san", "san"),
        # ("push", "push"),  # excluded: engine search noise
    )
    for name, kind in candidates:
        if not hasattr(board, name): continue
        if _mark_wrapped(board, name): continue
        original = getattr(board, name)

        def _mk_wrapper(fn, mode: str):
            def _wrapped(*args, **kwargs):
                # Pre-calc meta (best effort)
                san_hint = None
                from_sq = kwargs.get("from_sq")
                to_sq = kwargs.get("to_sq")
                promo = kwargs.get("promotion")
                try:
                    if mode == "san":
                        if args: san_hint = str(args[0])
                    else:
                        if len(args) >= 2:
                            from_sq, to_sq = str(args[0]), str(args[1])
                        promo = kwargs.get("promotion")
                        try:
                            import chess  # type: ignore
                            base = getattr(board, "board", None) or board
                            if hasattr(base, "san") and from_sq and to_sq:
                                uci = from_sq + to_sq + (promo.lower() if promo else "")
                                mv = chess.Move.from_uci(uci)
                                san_hint = base.san(mv)
                        except Exception:
                            pass
                except Exception:
                    pass

                ret = fn(*args, **kwargs)  # 실제 커밋

                # 불법/실패(ret is False)면 기록하지 않음
                if ret is False:
                    return ret

                try:
                    san = san_hint
                    if san is None and hasattr(board, "last_san"):
                        try: san = board.last_san()
                        except Exception: san = None
                    history.push(
                        board,
                        MoveMeta(
                            san=san or "?",
                            from_sq=from_sq or "?",
                            to_sq=to_sq or "?",
                            promotion=promo,
                        ),
                    )
                except Exception:
                    pass
                return ret
            return _wrapped

        setattr(board, name, _mk_wrapper(original, kind))

# ----------------------------
#  Record committed moves (Game side: apply_uci, etc.)
# ----------------------------
def _wrap_commit_methods_on_game(game: Any, board_for_push: Any, history: MoveHistory) -> None:
    candidates = ("apply_uci", "commit_move", "apply_move_uci", "play_move")
    for name in candidates:
        if not hasattr(game, name): continue
        if _mark_wrapped(game, name): continue
        original = getattr(game, name)

        def _mk_wrapper(fn):
            def _wrapped(*args, **kwargs):
                san_hint = None
                from_sq = kwargs.get("from_sq")
                to_sq = kwargs.get("to_sq")
                promo = kwargs.get("promotion")
                try:
                    uci = str(args[0]) if args else kwargs.get("uci")
                    if uci and len(uci) >= 4:
                        from_sq, to_sq = uci[:2], uci[2:4]
                        if len(uci) >= 5: promo = uci[4].upper()
                        try:
                            import chess  # type: ignore
                            base = getattr(board_for_push, "board", None) or board_for_push
                            if hasattr(base, "san"):
                                mv = chess.Move.from_uci(uci)
                                san_hint = base.san(mv)
                        except Exception:
                            pass
                except Exception:
                    pass

                ret = fn(*args, **kwargs)  # 실제 커밋

                # 불법/실패면 기록하지 않음
                if ret is False:
                    return ret

                try:
                    san = san_hint
                    if san is None and hasattr(board_for_push, "last_san"):
                        try: san = board_for_push.last_san()
                        except Exception: san = None
                    history.push(
                        board_for_push,
                        MoveMeta(
                            san=san or "?",
                            from_sq=from_sq or "?",
                            to_sq=to_sq or "?",
                            promotion=promo,
                        ),
                    )
                except Exception:
                    pass
                return ret
            return _wrapped

        setattr(game, name, _mk_wrapper(original))

# ----------------------------
#  Public API
# ----------------------------
def attach_replay(
    app: Any,
    *,
    snapshot_stride: int = 8,
    open_window: bool = True,
    window_geometry: str = "360x520+80+80",
) -> MoveHistory:
    """
    - Record only committed moves (skip illegal)
    - Use python-chess FEN snapshots
    - Auto-rebind when board/game objects are replaced
    - ReplayPanel shows busy cursor and triggers AI turn on jump
    """
    board, game = _resolve_board_and_game(app)
    redraw = _find_redraw(app)
    ai_tick = _find_ai_tick(app, game)
    busy = _make_busy(app)

    get_state, set_state, apply_move = _make_adapters(board)
    history = MoveHistory(get_state, set_state, apply_move, snapshot_stride=snapshot_stride)
    history.reset(board)

    _wrap_commit_methods_on_board(board, history)
    if game is not None:
        _wrap_commit_methods_on_game(game, board_for_push=board, history=history)

    # UI
    panel: Optional[ReplayPanel] = None
    if open_window:
        top = tk.Toplevel(app)
        top.title("Move History")
        try: top.geometry(window_geometry)
        except Exception: pass
        panel = ReplayPanel(top, board, history, redraw=redraw, on_jump=ai_tick, busy=busy)
        panel.pack(fill="both", expand=True)
        setattr(app, "_history_window", top)

    setattr(app, "_move_history", history)

    # Auto rebind (board/game replacement)
    last_ids = {"board": id(board), "game": id(game) if game is not None else None}
    def _rebinding():
        try:
            cur_board, cur_game = _resolve_board_and_game(app)
        except Exception:
            app.after(200, _rebinding); return

        changed = (id(cur_board) != last_ids["board"]) or ((id(cur_game) if cur_game else None) != last_ids["game"])
        if changed:
            last_ids["board"] = id(cur_board)
            last_ids["game"] = id(cur_game) if cur_game else None

            gs, ss, am = _make_adapters(cur_board)
            history.get_state = gs
            history.set_state = ss
            history.apply_move = am
            history.reset(cur_board)

            _wrap_commit_methods_on_board(cur_board, history)
            if cur_game is not None:
                _wrap_commit_methods_on_game(cur_game, board_for_push=cur_board, history=history)
            if panel is not None and hasattr(panel, "rebind"):
                try: panel.rebind(cur_board)
                except Exception: pass

        app.after(150, _rebinding)

    app.after(150, _rebinding)

    # Proactive trigger after new/reset/load if present
    for name in ("new_game", "reset_game", "start_new_game", "load_fen", "load_pgn", "open_pgn"):
        if hasattr(app, name) and callable(getattr(app, name)):
            orig = getattr(app, name)
            if _mark_wrapped(app, f"hook:{name}"): continue
            def _mk_wrapper(fn):
                def _w(*a, **kw):
                    r = fn(*a, **kw)
                    try: _rebinding()
                    finally: return r
                return _w
            setattr(app, name, _mk_wrapper(orig))

    return history

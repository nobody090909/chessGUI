from __future__ import annotations
import copy, tkinter as tk
from typing import Tuple
from history import MoveHistory, MoveMeta
from gui.replay import ReplayPanel

def _resolve_board(app) -> object:
    for path in ("board", "game", "game.board", "state.board", "ctx.board"):
        obj = app; ok = True
        for name in path.split("."):
            if hasattr(obj, name): obj = getattr(obj, name)
            else: ok = False; break
        if ok: return obj
    raise RuntimeError("Board object not found. Add your path in _resolve_board().")

def _mk_adapters(board) -> Tuple:
    if hasattr(board, "to_fen") and hasattr(board, "from_fen"):
        def get_state(b): return {"fen": b.to_fen()}
        def set_state(b, st): b.from_fen(st["fen"])
    elif hasattr(board, "to_dict") and hasattr(board, "from_dict"):
        def get_state(b): return copy.deepcopy(b.to_dict())
        def set_state(b, st): b.from_dict(copy.deepcopy(st))
    else:
        def get_state(b): return copy.deepcopy(b.__dict__)
        def set_state(b, st): b.__dict__.update(copy.deepcopy(st))

    def apply_move(b, m: MoveMeta):
        if hasattr(b, "apply_san") and m.san:
            b.apply_san(m.san); return
        fn = (getattr(b, "apply_move_algebraic", None) or
              getattr(b, "make_move", None) or
              getattr(b, "move", None) or
              getattr(b, "apply_move", None))
        if fn: fn(m.from_sq, m.to_sq, promotion=m.promotion); return
        raise RuntimeError("No move-apply method found on board.")

    return get_state, set_state, apply_move

def _wrap_apply_for_logging(board, history: MoveHistory):
    for name, kind in (("apply_move_algebraic","alg"), ("make_move","alg"),
                       ("move","alg"), ("apply_move","alg"),
                       ("apply_san","san"), ("push_san","san")):
        if not hasattr(board, name): continue
        orig = getattr(board, name)
        def _mk(fn, mode):
            def _w(*a, **kw):
                ret = fn(*a, **kw)
                try:
                    san = None; from_sq = to_sq = None; promo = kw.get("promotion")
                    if mode == "san":
                        san = str(a[0]) if a else kw.get("san")
                    else:
                        if len(a) >= 2: from_sq, to_sq = str(a[0]), str(a[1])
                    if san is None and hasattr(board, "last_san"):
                        try: san = board.last_san()
                        except Exception: san = None
                    history.push(board, MoveMeta(san=san or "?", from_sq=from_sq or "?", to_sq=to_sq or "?", promotion=promo))
                except Exception: pass
                return ret
            return _w
        setattr(board, name, _mk(orig, kind))

def attach_replay(app, snapshot_stride: int = 8):
    """ChessApp에서 호출: 이동 이력/리플레이를 보조창(Toplevel)으로 부착."""
    board = _resolve_board(app)
    get_state, set_state, apply_move = _mk_adapters(board)
    history = MoveHistory(get_state, set_state, apply_move, snapshot_stride=snapshot_stride)
    history.reset(board)
    _wrap_apply_for_logging(board, history)  # 이미 push하면 제거 가능

    top = tk.Toplevel(app); top.title("Move History"); top.geometry("360x520+80+80")
    ReplayPanel(top, board, history).pack(fill="both", expand=True)

    app._move_history = history
    app._history_window = top
    return history

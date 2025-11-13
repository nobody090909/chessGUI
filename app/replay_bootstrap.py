from __future__ import annotations

import copy
import tkinter as tk
from typing import Any, Callable, Optional, Tuple

from app.history import MoveHistory, MoveMeta
from app.gui.replay import ReplayPanel


# ----------------------------
#  Board / Game 객체 탐색
# ----------------------------
def _resolve_board_and_game(app: Any) -> Tuple[Any, Optional[Any]]:
    if hasattr(app, "board"):
        board = getattr(app, "board")
        game = getattr(app, "game", None) if hasattr(app, "game") else None
        return board, game
    if hasattr(app, "game") and hasattr(app.game, "board"):
        return app.game.board, app.game
    for attr0 in ("state", "ctx"):
        if hasattr(app, attr0) and hasattr(getattr(app, attr0), "board"):
            return getattr(getattr(app, attr0), "board"), getattr(app, "game", None)
    raise RuntimeError("Board object not found.")


# ----------------------------
#  상태 스냅샷/복원/재적용 어댑터
# ----------------------------
def _make_adapters(board: Any) -> Tuple[
    Callable[[Any], Any],
    Callable[[Any, Any], None],
    Callable[[Any, MoveMeta], None],
]:
    if hasattr(board, "fen") and hasattr(board, "set_fen"):
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
        if hasattr(b, "apply_san") and m.san:
            b.apply_san(m.san); return
        if hasattr(b, "push") and m.from_sq and m.to_sq:
            try:
                import chess  # type: ignore
                mv = chess.Move.from_uci(m.from_sq + m.to_sq + (m.promotion.lower() if m.promotion else ""))
                b.push(mv); return
            except Exception:
                pass
        for name in ("apply_move_algebraic", "make_move", "move", "apply_move"):
            fn = getattr(b, name, None)
            if fn:
                fn(m.from_sq, m.to_sq, promotion=m.promotion); return
        raise RuntimeError("apply_move: no suitable method on board for replay")

    return get_state, set_state, apply_move


# ----------------------------
#  리렌더/AI tick/Busy 콜백 탐색
# ----------------------------
def _find_redraw(app: Any) -> Callable[[], None]:
    for n in ("redraw_board", "draw_board", "render_board", "refresh", "redraw", "update_board", "repaint"):
        fn = getattr(app, n, None)
        if callable(fn): return fn
    return lambda: None

def _find_ai_tick(app: Any, game: Optional[Any]) -> Callable[[], None]:
    names = ("maybe_ai_turn", "ai_move_if_needed", "ai_play", "engine_move", "play_ai_turn", "ai_step")
    for owner in (app, game):
        if owner is None: continue
        for n in names:
            fn = getattr(owner, n, None)
            if callable(fn): return fn
    return lambda: None

def _make_busy(app: Any):
    def busy(on: bool) -> None:
        try:
            app.config(cursor="watch" if on else "")
            app.update_idletasks()
            app.update()
        except Exception:
            pass
    return busy


# ----------------------------
#  커밋 지점만 기록(탐색 push/pop 제외)
# ----------------------------
def _wrap_commit_methods_on_board(board: Any, history: MoveHistory) -> None:
    candidates = (
        ("apply_move_algebraic", "alg"),
        ("make_move", "alg"),
        ("move", "alg"),
        ("apply_move", "alg"),
        ("apply_san", "san"),
        ("push_san", "san"),
    )
    for name, kind in candidates:
        if not hasattr(board, name):
            continue
        original = getattr(board, name)

        def _mk_wrapper(fn, mode: str):
            def _wrapped(*args, **kwargs):
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

                ret = fn(*args, **kwargs)

                try:
                    san = san_hint
                    if san is None and hasattr(board, "last_san"):
                        try: san = board.last_san()
                        except Exception: san = None
                    history.push(board, MoveMeta(
                        san=san or "?",
                        from_sq=from_sq or "?",
                        to_sq=to_sq or "?",
                        promotion=promo
                    ))
                except Exception:
                    pass
                return ret
            return _wrapped

        setattr(board, name, _mk_wrapper(original, kind))


def _wrap_commit_methods_on_game(game: Any, board_for_push: Any, history: MoveHistory) -> None:
    candidates = ("apply_uci", "commit_move", "apply_move_uci", "play_move")
    for name in candidates:
        if not hasattr(game, name):
            continue
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
                        if len(uci) >= 5:
                            promo = uci[4].upper()
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

                ret = fn(*args, **kwargs)

                try:
                    san = san_hint
                    if san is None and hasattr(board_for_push, "last_san"):
                        try: san = board_for_push.last_san()
                        except Exception: san = None
                    history.push(board_for_push, MoveMeta(
                        san=san or "?",
                        from_sq=from_sq or "?",
                        to_sq=to_sq or "?",
                        promotion=promo
                    ))
                except Exception:
                    pass
                return ret
            return _wrapped

        setattr(game, name, _mk_wrapper(original))


# ----------------------------
#  새 게임/포지션 로딩 감지 → 히스토리 리셋
# ----------------------------
def _wrap_new_game_hooks(app: Any,
                         panel: ReplayPanel,
                         board_ref: list[Any],
                         history: MoveHistory,
                         rewrap_commit: Callable[[Any, Optional[Any]], None],
                         redraw: Callable[[], None]) -> None:
    """
    - new game / reset / load FEN/PGN 등의 메서드를 래핑.
    - 호출 후 보드가 바뀌었으면 rebind + history.reset 수행.
    """
    candidates = (
        "new_game", "reset_game", "start_new_game", "restart",
        "load_fen", "load_pgn", "set_position", "setup_startpos",
        "create_new_game", "init_game",
    )
    def _after():
        # 보드 재탐색
        new_board, new_game = _resolve_board_and_game(app)
        if new_board is not board_ref[0]:
            board_ref[0] = new_board
            panel.rebind(new_board)                 # 패널 보드 교체
            rewrap_commit(new_board, new_game)      # 커밋 래퍼 재설치
        history.reset(new_board)                    # 히스토리 초기화
        redraw()

    for name in candidates:
        if not hasattr(app, name):
            continue
        original = getattr(app, name)
        def _mk_wrapper(fn):
            def _wrapped(*a, **kw):
                out = fn(*a, **kw)
                _after()
                return out
            return _wrapped
        setattr(app, name, _mk_wrapper(original))


# ----------------------------
#  공개 API
# ----------------------------
def attach_replay(
    app: Any,
    *,
    snapshot_stride: int = 6,                 # 더 촘촘한 스냅샷로 점프 속도 개선
    open_window: bool = True,
    window_geometry: str = "360x520+80+80",
) -> MoveHistory:
    """
    - 엔진 탐색(push/pop)은 기록하지 않고, 최종 커밋된 수만 기록.
    - 히스토리 이동 시 보드 리렌더 및 AI 턴 자동 트리거.
    - 새 게임/포지션 로딩 시 히스토리 자동 초기화.
    """
    board, game = _resolve_board_and_game(app)
    redraw = _find_redraw(app)
    ai_tick = _find_ai_tick(app, game)
    busy = _make_busy(app)

    get_state, set_state, apply_move = _make_adapters(board)
    history = MoveHistory(get_state, set_state, apply_move, snapshot_stride=snapshot_stride)
    history.reset(board)

    # 커밋 지점 래핑
    def _rewrap_commit(new_board: Any, new_game: Optional[Any]) -> None:
        _wrap_commit_methods_on_board(new_board, history)
        if new_game is not None:
            _wrap_commit_methods_on_game(new_game, board_for_push=new_board, history=history)

    _rewrap_commit(board, game)

    # 리플레이 패널
    if open_window:
        top = tk.Toplevel(app)
        top.title("Move History")
        try:
            top.geometry(window_geometry)
        except Exception:
            pass
        panel = ReplayPanel(top, board, history, redraw=redraw, on_jump=ai_tick, busy=busy)
        panel.pack(fill="both", expand=True)
        setattr(app, "_history_window", top)
    else:
        panel = ReplayPanel(app, board, history, redraw=redraw, on_jump=ai_tick, busy=busy)

    # 새 게임/포지션 로딩 훅
    board_ref = [board]
    _wrap_new_game_hooks(app, panel, board_ref, history, _rewrap_commit, redraw)

    # 히스토리 변경 시(되감기 포함) 화면 갱신
    history.bind_on_change(lambda _c, _t: redraw())

    setattr(app, "_move_history", history)
    return history

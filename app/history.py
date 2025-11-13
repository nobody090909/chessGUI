from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
import copy

State = Any

@dataclass
class MoveMeta:
    san: str
    from_sq: str
    to_sq: str
    promotion: Optional[str] = None
    captured: Optional[str] = None
    is_castle: bool = False
    is_enpassant: bool = False

class MoveHistory:
    """선형 타임라인 + 스냅샷 stride로 임의 시점 점프 가속"""
    def __init__(
        self,
        get_state: Callable[[Any], State],
        set_state: Callable[[Any, State], None],
        apply_move: Callable[[Any, MoveMeta], None],
        snapshot_stride: int = 8
    ):
        self.get_state = get_state
        self.set_state = set_state
        self.apply_move = apply_move
        self.snapshot_stride = max(1, snapshot_stride)
        self._moves: List[MoveMeta] = []
        self._snapshots: Dict[int, State] = {}
        self._cursor: int = 0
        self._on_change: Optional[Callable[[int, int], None]] = None

    def bind_on_change(self, cb: Callable[[int, int], None]) -> None:
        self._on_change = cb

    def _fire(self) -> None:
        if self._on_change:
            self._on_change(self._cursor, len(self._moves))

    def reset(self, board: Any) -> None:
        self._moves.clear()
        self._snapshots.clear()
        self._cursor = 0
        self._snapshots[0] = copy.deepcopy(self.get_state(board))
        self._fire()

    def push(self, board: Any, move: MoveMeta) -> None:
        if self._cursor < len(self._moves):
            del self._moves[self._cursor:]
            for k in list(self._snapshots.keys()):
                if k > self._cursor:
                    self._snapshots.pop(k, None)
        self._moves.append(move)
        self._cursor += 1
        if self._cursor % self.snapshot_stride == 0:
            self._snapshots[self._cursor] = copy.deepcopy(self.get_state(board))
        self._fire()

    @property
    def cursor(self) -> int: return self._cursor
    @property
    def total(self) -> int: return len(self._moves)
    def moves(self) -> List[MoveMeta]: return list(self._moves)

    def goto(self, board: Any, target_index: int) -> None:
        if not (0 <= target_index <= len(self._moves)):
            raise IndexError(f"goto out of range: {target_index}")
        if target_index == self._cursor:
            return
        snap = max([i for i in self._snapshots.keys() if i <= target_index], default=0)
        self.set_state(board, copy.deepcopy(self._snapshots[snap]))
        for i in range(snap, target_index):
            self.apply_move(board, self._moves[i])
        self._cursor = target_index
        self._fire()

    def first(self, board: Any) -> None: self.goto(board, 0)
    def last(self, board: Any) -> None: self.goto(board, len(self._moves))
    def prev(self, board: Any) -> None:
        if self._cursor > 0: self.goto(board, self._cursor - 1)
    def next(self, board: Any) -> None:
        if self._cursor < len(self._moves): self.goto(board, self._cursor + 1)

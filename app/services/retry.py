from __future__ import annotations
import time
from typing import Callable, TypeVar, Tuple

T = TypeVar("T")

def retry(fn: Callable[[], T], *, attempts: int = 3, backoff: float = 0.5) -> Tuple[bool, T | None, Exception | None]:
    last_exc = None
    for i in range(attempts):
        try:
            return True, fn(), None
        except Exception as e:
            last_exc = e
            time.sleep(backoff * (2 ** i))
    return False, None, last_exc

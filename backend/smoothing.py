from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple


class MovingAverageSmoother:
    """Lightweight moving average smoother for 2D positions (normalized 0..1)."""

    def __init__(self, window: int = 5):
        self.window = max(1, int(window))
        self._xs: Deque[float] = deque(maxlen=self.window)
        self._ys: Deque[float] = deque(maxlen=self.window)

    def reset(self) -> None:
        self._xs.clear()
        self._ys.clear()

    def update(self, x: float, y: float) -> Tuple[float, float]:
        self._xs.append(float(x))
        self._ys.append(float(y))

        avg_x = sum(self._xs) / len(self._xs)
        avg_y = sum(self._ys) / len(self._ys)
        return avg_x, avg_y


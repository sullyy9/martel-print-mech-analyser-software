from dataclasses import dataclass
from typing import Self

import numpy as np

@dataclass
class Point:
    x: int
    y: int

    def __add__(self, rhs: Self) -> Self:
        return Point(self.x + rhs.x, self.y + rhs.y)

    def __sub__(self, rhs: Self) -> Self:
        return Point(self.x - rhs.x, self.y - rhs.y)


@dataclass
class Span:
    beg: int
    end: int

    @property
    def len(self) -> int:
        return self.end - self.beg

    @property
    def slice(self) -> slice:
        return slice(self.beg, self.end)


@dataclass
class BoundingBox:
    p1: Point
    p2: Point

    @classmethod
    def from_spans(cls, xspan: Span, yspan: Span) -> Self:
        return cls(
            Point(xspan.beg, yspan.beg),
            Point(xspan.end, yspan.end),
        )

    @property
    def width(self) -> int:
        return self.p2.x - self.p1.x

    @property
    def height(self) -> int:
        return self.p2.y - self.p1.y

    @property
    def center(self) -> Point:
        return Point(
            self.p1.x + int((self.p2.x - self.p1.x) / 2),
            self.p1.y + int((self.p2.y - self.p1.y) / 2),
        )

    @property
    def slice(self) -> tuple[slice, slice]:
        return np.index_exp[self.p1.y : self.p2.y, self.p1.x : self.p2.x]

    @property
    def horizontal_span(self) -> Span:
        return Span(self.p1.x, self.p2.x)

    @property
    def vertical_span(self) -> Span:
        return Span(self.p1.y, self.p2.y)

    def clamp(self, bbox: Self) -> Self:
        return BoundingBox(
            Point(
                max(min(self.p1.x, bbox.p2.x), bbox.p1.x),
                max(min(self.p1.y, bbox.p2.y), bbox.p1.y),
            ),
            Point(
                max(min(self.p2.x, bbox.p2.x), bbox.p1.x),
                max(min(self.p2.y, bbox.p2.y), bbox.p1.y),
            ),
        )

from pathlib import Path
from typing import Final, Optional, Self

import cv2 as cv
import numpy as np
from numpy import uint8
from numpy.typing import NDArray

from print_mech_analyser.printout import Printout
from print_mech_analyser.geometry import Span, BoundingBox

Color: Final = tuple[int, int, int]


class PrettyPrintout(np.lib.mixins.NDArrayOperatorsMixin):
    __slots__ = ["_img"]

    _WINODW_NAME_INDEX: int = 0

    def __init__(self, image: NDArray[uint8]) -> None:
        if len(image.shape) != 3:
            raise TypeError("Too many dimensions in image")

        self._img: NDArray[uint8] = image

    @classmethod
    def from_printout(cls, printout: Printout) -> Self:
        return cls(
            np.where(
                np.expand_dims(printout._img, 2) == 0, (255, 255, 255), (0, 0, 0)
            ).astype(uint8)
        )

    def __array__(self, dtype=uint8) -> NDArray[uint8]:
        return self._img.astype(dtype)

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs) -> Self:
        inputs = [i._img if isinstance(i, self.__class__) else i for i in inputs]

        match method:
            case "__call__":
                return self.__class__(ufunc(*inputs, **kwargs))
            case "reduce":
                return ufunc.reduce(*inputs, **kwargs)
            case "accumulate":
                return ufunc.accumulate(*inputs, **kwargs)
            case "outer":
                return self.__class__(ufunc.outer(*inputs, **kwargs))
            case _:
                return NotImplemented

    def __getitem__(self, index) -> Self:
        return self.__class__(self._img.__getitem__(index))

    def __len__(self) -> int:
        return len(self._img)

    @property
    def length(self) -> int:
        return self._img.shape[0]

    @property
    def width(self) -> int:
        return self._img.shape[1]

    @property
    def size(self) -> tuple[int, int]:
        return (self._img.shape[0], self._img.shape[1])

    @property
    def shape(self) -> tuple[int, ...]:
        return self._img.shape

    def highlight_strip(self, span: Span, color: tuple[int, int, int]) -> None:
        """
        Description
        -----------
        Highlight a horizontal strip in the printout.

        """
        area: Final = np.array(self[span.slice, :])
        highlight: Final = np.full(area.shape, color, dtype=uint8)

        self._img[span.slice, :] = cv.addWeighted(area, 0.5, highlight, 0.5, 1.0)

    def highlight_area(self, bounds: BoundingBox, color: Color) -> None:
        """
        Description
        -----------
        Highlight a rectangular area in the printout.

        """
        area: Final = np.array(self[bounds.slice])
        highlight: Final = np.full(area.shape, color, dtype=uint8)

        highlighted_area = cv.addWeighted(area, 0.5, highlight, 0.5, 1.0)

        self._img[bounds.slice] = highlighted_area

    def save(self, path: Path) -> None:
        cv.imwrite(str(path.absolute()), np.array(self))

    def show(
        self, window_name: Optional[str] = None, wait: bool = False, split: bool = False
    ) -> None:
        # Base window name
        base_window_name: str = ""
        if window_name is None:
            base_window_name = "Pretty Printout " + str(self._WINODW_NAME_INDEX)
            Printout._WINODW_NAME_INDEX += 1
        else:
            base_window_name = window_name

        if not split:
            cv.imshow(base_window_name, self._img)
            cv.waitKey() if wait else ...
            return

        # If the image should be split into multiple parts when too large.
        for i, beg in enumerate(range(0, self.length, 720)):
            name: str = base_window_name + f" - {i}"
            len: int = min(self.length - beg, 720)
            end: int = beg + len
            cv.imshow(name, self._img[beg:end, :])

        cv.waitKey() if wait else ...

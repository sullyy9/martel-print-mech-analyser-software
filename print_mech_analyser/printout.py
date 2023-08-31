from pathlib import Path
from typing import Final, Optional, Self

import cv2 as cv
import numpy as np
from numpy import uint8
from numpy.typing import NDArray

WHITE: Final = 255
BLACK: Final = 0


class Printout(np.lib.mixins.NDArrayOperatorsMixin):
    __slots__ = ["_img"]

    _WINODW_NAME_INDEX: int = 0

    def __init__(self, img: NDArray[uint8]) -> None:
        if len(img.shape) > 2:
            raise TypeError("Too many dimensions in printout image.")

        self._img: NDArray[uint8] = img

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

    @classmethod
    def from_file(cls, filepath: Path) -> Self:
        """
        Load a printout from a file.

        Parameters
        ----------
        filepath : Path
            Path to a greyscale, 8 bits per pixel image.

        Returns
        -------
        Self

        Raises
        ------
        FileNotFoundError
            If the file doesn't exist.

        """
        if not filepath.exists():
            raise FileNotFoundError(f"File {filepath} does not exist.")

        image: NDArray = cv.imread(str(filepath), cv.IMREAD_GRAYSCALE)
        if image.dtype != uint8:
            raise ValueError("Image must be 8bpp")

        return cls(image.astype(uint8))

    @classmethod
    def blank(cls, width: int, length: int) -> Self:
        return Printout(np.zeros((length, width), dtype=uint8))

    @property
    def length(self) -> int:
        return self._img.shape[0]

    @property
    def width(self) -> int:
        return self._img.shape[1]

    @property
    def size(self) -> tuple[int, int]:
        return self._img.shape[:2]

    def save(self, path: Path) -> None:
        cv.imwrite(str(path.absolute()), np.array(self))

    def show(self, window_name: Optional[str] = None, wait: bool = False) -> None:
        if window_name is None:
            window_name = "Printout " + str(self._WINODW_NAME_INDEX)
            Printout._WINODW_NAME_INDEX += 1

        cv.imshow(window_name, self._img)
        cv.waitKey() if wait else ...

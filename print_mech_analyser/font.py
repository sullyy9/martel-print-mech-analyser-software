import math
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Self, Sequence

import cv2 as cv
import numpy as np
from numpy import ndarray, uint8
from numpy.typing import NDArray


@dataclass
class Font:
    name: str
    width: int
    height: int
    code_points: list[int]
    glyphs: list[NDArray[uint8]]
    contours: list[Sequence] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        for glyph in self.glyphs:
            contours = cv.findContours(glyph, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)[0]
            self.contours.append(contours)

    @classmethod
    def from_json(cls, filepath: Path):
        json_data: dict = {}
        with open(filepath, "r") as file:
            json_data = json.load(file)

        name: Final[str] = json_data["name"]
        width: Final[int] = json_data["glyph_width"]
        height: Final[int] = json_data["glyph_height"]

        row_bytes: Final[int] = math.ceil(width / 8.0)

        json_glyphs: dict[str, list[int]] = json_data["glyphs"]

        code_points: list[int] = [int(cp, base=16) for cp in json_glyphs.keys()]
        glyphs: list[NDArray[uint8]] = []
        for glyph_data in json_glyphs.values():
            # Turn the 1 bpp 1D array into 8bpp 2D.
            data = np.array(glyph_data, dtype=uint8).reshape((-1, row_bytes))
            data = np.where(np.unpackbits(data, axis=1) != 0, 255, 0).astype(uint8)
            glyphs.append(data)

        return cls(name, width, height, code_points, glyphs)

    def into_bold(self) -> Self:
        def make_bold(glyph: NDArray[uint8]) -> NDArray[uint8]:
            glyph = np.packbits(np.where(glyph != 0, 1, 0).astype(uint8), axis=1)

            # Apply the bold algorithm, taken from the printer firmware.
            row_count = glyph.shape[0]
            for r in range(0, row_count):
                glyph[r, 1] |= glyph[r, 1] >> 1 | glyph[r, 0] << 7
                glyph[r, 0] |= glyph[r, 0] >> 1

            return np.where(np.unpackbits(glyph, axis=1) != 0, 255, 0).astype(uint8)

        name: Final[str] = self.name + "-bold"
        bold_glyphs: list[NDArray[uint8]] = [make_bold(glyph) for glyph in self.glyphs]

        return Font(name, self.width, self.height, self.code_points, bold_glyphs)

    def show_char(self, code_point: int) -> None:
        cv.imshow(f"{self.name} : {code_point}", self.glyphs[code_point])
        cv.waitKey()

    def show(self, glyphs_per_row: int = 32, grid: bool = False) -> None:
        rows: list[ndarray] = []
        row_count = math.ceil(len(self.glyphs) / glyphs_per_row)

        for i in range(row_count):
            beg, end = glyphs_per_row * i, glyphs_per_row * (i + 1)
            row_glyphs = self.glyphs[beg:end]

            # Add vertical grid lines if nescessary.
            if grid:
                for i in range(0, (len(row_glyphs) * 2) + 1, 2):
                    row_glyphs.insert(i, np.full((self.height, 1), 255, dtype=uint8))

            rows.append(np.hstack(row_glyphs, dtype=uint8))

        # Check if the final row needs some padding.
        row_width = glyphs_per_row * self.width
        if grid:
            row_width += glyphs_per_row + 1

        if rows[-1].shape[1] < row_width:
            padding_width = row_width - rows[-1].shape[1]
            padding = np.zeros((self.height, padding_width), dtype=uint8)
            rows[-1] = np.hstack((rows[-1], padding), dtype=uint8)

        # Add horizontal grid lines if nescessary.
        if grid:
            for i in range(0, (len(rows) * 2) + 1, 2):
                rows.insert(i, np.full((1, row_width), 255, dtype=uint8))

        cv.imshow("Font", np.vstack(rows, dtype=uint8))
        cv.waitKey()

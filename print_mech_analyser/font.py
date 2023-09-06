import math
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import cv2 as cv
import numpy as np
from numpy import ndarray, uint8
from numpy.typing import NDArray


@dataclass
class CharMatch:
    char: str
    match: float


class Font:
    MATCH_THRESHOLD: Final[float] = 0.01

    def __init__(self, filepath: Path):
        self.name: str
        self.glyph_width: int
        self.glyph_height: int
        self._glyphs: dict[int, ndarray] = {}
        self._glyph_contours: dict[int, Any] = {}

        with open(filepath, "r") as file:
            data = json.load(file)
            self.name = data["name"]
            self.glyph_width = data["glyph_width"]
            self.glyph_height = data["glyph_height"]

            row_bytes = math.ceil(self.glyph_width / 8.0)

            glyphs: dict[str, list[int]] = data["glyphs"]
            for cp, glyph_data in glyphs.items():
                code_point = int(cp, base=16)
                # Turn the 1 bpp 1D array into 8bpp 2D.
                data = np.array(glyph_data, dtype=uint8).reshape((-1, row_bytes))
                data = np.unpackbits(data, axis=1)
                data = np.where(data != 0, 255, 0).astype(uint8)

                self._glyphs[code_point] = data
                self._glyph_contours[code_point], _ = cv.findContours(
                    data, cv.RETR_LIST, cv.CHAIN_APPROX_NONE
                )

    def show_char(self, code_point: int) -> None:
        cv.imshow(f"Character: {code_point}", self._glyphs[code_point])
        cv.waitKey()

    def show(self, glyphs_per_row: int = 32) -> None:
        glyphs = [glyph for glyph in self._glyphs.values()]

        rows: list[ndarray] = []
        row_count = math.ceil(len(self._glyphs) / glyphs_per_row)

        for i in range(row_count):
            beg = glyphs_per_row * i
            end = glyphs_per_row * (i + 1)
            rows.append(np.hstack(glyphs[beg:end], dtype=uint8))

        # Check if the final row needs some padding.
        row_width = glyphs_per_row * self.glyph_width
        if rows[-1].shape[1] < row_width:
            padding_width = row_width - rows[-1].shape[1]
            padding = np.zeros((self.glyph_height, padding_width), dtype=uint8)
            rows[-1] = np.hstack((rows[-1], padding), dtype=uint8)

        cv.imshow("Font", np.vstack(rows, dtype=uint8))
        cv.waitKey()

    def parse_image(self, image: NDArray[uint8]) -> list[CharMatch]:
        # Pad the image if nescessary
        width = image.shape[1]
        height = image.shape[0]

        xpad = self.glyph_width - width if width < self.glyph_width else 0
        ypad = self.glyph_height - height if height < self.glyph_height else 0

        image = np.pad(
            image,
            pad_width=(
                (math.floor(ypad / 2), math.ceil(ypad / 2)),
                (math.floor(xpad / 2), math.ceil(xpad / 2)),
            ),
        )

        image_contours, _ = cv.findContours(image, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)

        # If no contours then it's probably whitespace.
        # TODO return list of possible whitespace chars instead.
        if len(image_contours) == 0:
            spaces = math.floor(image.shape[1] / self.glyph_width)
            return [CharMatch("".join([" " for _ in range(spaces)]), 0.0)]

        matches: list[CharMatch] = []
        for code, glyph_contours in self._glyph_contours.items():
            # If there are no contours then it's a blank image / glyph.
            if len(glyph_contours) != len(image_contours):
                continue

            match_sum = 0
            for image_contour, glyph_contour in zip(image_contours, glyph_contours):
                match_sum += cv.matchShapes(
                    image_contour, glyph_contour, cv.CONTOURS_MATCH_I1, 0.0
                )
            match = match_sum / len(glyph_contours)

            if match < self.MATCH_THRESHOLD:
                matches.append(CharMatch(chr(code), match))

        return matches

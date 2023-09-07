import math
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Self

import cv2 as cv
import numpy as np
from numpy import ndarray, uint8
from numpy.typing import NDArray


@dataclass
class CharMatch:
    char: str
    font: str
    code_point: int
    match: float


class Font:
    MATCH_THRESHOLD: Final[float] = 0.01

    def __init__(
        self,
        name: str,
        glyph_width: int,
        glyph_height: int,
        glyphs: dict[int, NDArray[uint8]],
    ) -> None:
        self.name: str = name
        self.glyph_width: int = glyph_width
        self.glyph_height: int = glyph_height
        self._glyphs: dict[int, ndarray] = glyphs
        self._glyph_contours: dict[int, Any] = {}

        for cp, glyph in glyphs.items():
            self._glyph_contours[cp], _ = cv.findContours(
                glyph, cv.RETR_LIST, cv.CHAIN_APPROX_NONE
            )

    @classmethod
    def from_json(cls, filepath: Path):
        json_data: dict = {}
        with open(filepath, "r") as file:
            json_data = json.load(file)

        name = json_data["name"]
        glyph_width = json_data["glyph_width"]
        glyph_height = json_data["glyph_height"]

        row_bytes = math.ceil(glyph_width / 8.0)

        json_glyphs: dict[str, list[int]] = json_data["glyphs"]
        glyphs: dict[int, NDArray[uint8]] = {}

        for cp, glyph_data in json_glyphs.items():
            code_point = int(cp, base=16)
            # Turn the 1 bpp 1D array into 8bpp 2D.
            data = np.array(glyph_data, dtype=uint8).reshape((-1, row_bytes))
            data = np.unpackbits(data, axis=1)
            data = np.where(data != 0, 255, 0).astype(uint8)

            glyphs[code_point] = data

        return cls(
            name=name,
            glyph_width=glyph_width,
            glyph_height=glyph_height,
            glyphs=glyphs,
        )

    def into_bold(self) -> Self:
        bold_glyphs: dict[int, ndarray] = {}

        for cp, glyph in self._glyphs.items():
            glyph = np.where(glyph != 0, 1, 0).astype(uint8)
            glyph = np.packbits(glyph, axis=1)

            # Apply the bold algorithm, taken from the printer firmware.
            rows = glyph.shape[0]
            for r in range(0, rows):
                glyph[r, 1] |= glyph[r, 1] >> 1 | glyph[r, 0] << 7
                glyph[r, 0] |= glyph[r, 0] >> 1

            glyph = np.unpackbits(glyph, axis=1)
            glyph = np.where(glyph != 0, 255, 0).astype(uint8)
            bold_glyphs[cp] = glyph

        return Font(
            name=self.name + "-bold",
            glyph_width=self.glyph_width,
            glyph_height=self.glyph_height,
            glyphs=bold_glyphs,
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
            return [
                CharMatch(
                    char="".join([" " for _ in range(spaces)]),
                    font=self.name,
                    code_point=0x20,
                    match=0.0,
                )
            ]

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
                matches.append(
                    CharMatch(
                        char=chr(code),
                        font=self.name,
                        code_point=code,
                        match=match,
                    )
                )

        return matches

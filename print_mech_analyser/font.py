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
    TEMPLATE_THRESHOLD: Final[float] = 100
    CONTOUR_THRESHOLD: Final[float] = 0.1

    def __init__(
        self,
        name: str,
        glyph_width: int,
        glyph_height: int,
        code_points: list[int],
        glyphs: list[NDArray[uint8]],
    ) -> None:
        self.name: str = name
        self.glyph_width: int = glyph_width
        self.glyph_height: int = glyph_height

        self._code_points: list[int] = code_points
        self._glyphs: list[NDArray[uint8]] = glyphs
        self._contours: list[Any] = []

        for glyph in glyphs:
            contours, _ = cv.findContours(glyph, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)
            self._contours.append(contours)

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

        code_points: list[int] = []
        glyphs: list[NDArray[uint8]] = []
        for cp, glyph_data in json_glyphs.items():
            code_point = int(cp, base=16)
            # Turn the 1 bpp 1D array into 8bpp 2D.
            data = np.array(glyph_data, dtype=uint8).reshape((-1, row_bytes))
            data = np.unpackbits(data, axis=1)
            data = np.where(data != 0, 255, 0).astype(uint8)

            code_points.append(code_point)
            glyphs.append(data)

        return cls(
            name=name,
            glyph_width=glyph_width,
            glyph_height=glyph_height,
            code_points=code_points,
            glyphs=glyphs,
        )

    def into_bold(self) -> Self:
        bold_glyphs: list[NDArray[uint8]] = []

        for glyph in self._glyphs:
            glyph = np.where(glyph != 0, 1, 0).astype(uint8)
            glyph = np.packbits(glyph, axis=1)

            # Apply the bold algorithm, taken from the printer firmware.
            rows = glyph.shape[0]
            for r in range(0, rows):
                glyph[r, 1] |= glyph[r, 1] >> 1 | glyph[r, 0] << 7
                glyph[r, 0] |= glyph[r, 0] >> 1

            glyph = np.unpackbits(glyph, axis=1)
            glyph = np.where(glyph != 0, 255, 0).astype(uint8)
            bold_glyphs.append(glyph)

        return Font(
            name=self.name + "-bold",
            glyph_width=self.glyph_width,
            glyph_height=self.glyph_height,
            code_points=self._code_points,
            glyphs=bold_glyphs,
        )

    def show_char(self, code_point: int) -> None:
        cv.imshow(f"Character: {code_point}", self._glyphs[code_point])
        cv.waitKey()

    def show(self, glyphs_per_row: int = 32) -> None:
        rows: list[ndarray] = []
        row_count = math.ceil(len(self._glyphs) / glyphs_per_row)

        for i in range(row_count):
            beg = glyphs_per_row * i
            end = glyphs_per_row * (i + 1)
            rows.append(np.hstack(self._glyphs[beg:end], dtype=uint8))

        # Check if the final row needs some padding.
        row_width = glyphs_per_row * self.glyph_width
        if rows[-1].shape[1] < row_width:
            padding_width = row_width - rows[-1].shape[1]
            padding = np.zeros((self.glyph_height, padding_width), dtype=uint8)
            rows[-1] = np.hstack((rows[-1], padding), dtype=uint8)

        cv.imshow("Font", np.vstack(rows, dtype=uint8))
        cv.waitKey()

    def parse_image(self, image: NDArray[uint8]) -> list[CharMatch]:
        # If image is whitespace whitespace.
        # TODO return list of possible whitespace chars instead.
        if not np.any(image):
            spaces = math.floor(image.shape[1] / self.glyph_width)
            return [
                CharMatch(
                    char="".join([" " for _ in range(spaces)]),
                    font=self.name,
                    code_point=0x20,
                    match=0.0,
                )
            ]

        # Pad the image if nescessary.
        width = image.shape[1]
        height = image.shape[0]

        xpad = self.glyph_width - width if width < self.glyph_width else 0
        ypad = self.glyph_height - height if height < self.glyph_height else 0

        image = np.pad(
            image,
            pad_width=(
                (ypad, ypad),
                (xpad, xpad),
            ),
        )

        image_contours, _ = cv.findContours(image, cv.RETR_LIST, cv.CHAIN_APPROX_NONE)

        # Find a set of matches using the relatively fast contour matching technique.
        # Contour matching is scale and rotation invariant so may give some false
        # positives.
        def match_contours(contours) -> float:
            match_sum = 0
            for image_contour, glyph_contour in zip(image_contours, contours):
                match_sum += cv.matchShapes(
                    image_contour, glyph_contour, cv.CONTOURS_MATCH_I1, 0.0
                )
            return match_sum / len(contours)

        matches = enumerate(self._contours)
        matches = filter(lambda cont: len(cont[1]) != 0, matches)
        matches = map(lambda cont: (cont[0], match_contours(cont[1])), matches)
        matches = filter(lambda match: match[1] < self.CONTOUR_THRESHOLD, matches)

        # Refine the match set using template matching.
        def match_template(glyph: NDArray[uint8]) -> float:
            min, _, _, _ = cv.minMaxLoc(cv.matchTemplate(image, glyph, cv.TM_SQDIFF))
            return min

        matches = map(lambda match: (match[0], self._glyphs[match[0]]), matches)
        matches = map(lambda match: (match[0], match_template(match[1])), matches)
        matches = filter(lambda match: match[1] < self.TEMPLATE_THRESHOLD, matches)

        return [
            CharMatch(
                char=chr(self._code_points[i]),
                font=self.name,
                code_point=self._code_points[i],
                match=match,
            )
            for i, match in matches
        ]

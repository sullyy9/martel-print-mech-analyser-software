import math
import json
from dataclasses import dataclass
from pathlib import Path

import cv2 as cv
import numpy as np
from numpy import ndarray, uint8
from numpy.typing import NDArray


class Font:
    def __init__(self, filepath: Path):
        self.name: str
        self.glyph_width: int
        self.glyph_height: int
        self._glyphs: dict[int, ndarray] = {}

        with open(filepath, "r") as file:
            data = json.load(file)
            self.name = data["name"]
            self.glyph_width = data["glyph_width"]
            self.glyph_height = data["glyph_height"]

            row_bytes = math.ceil(self.glyph_width / 8.0)

            glyphs: dict[str, list[int]] = data["glyphs"]
            for cp, glyph_data in glyphs.items():
                # Turn the 1 bpp 1D array into 8bpp 2D.
                data = np.array(glyph_data, dtype=uint8).reshape((-1, row_bytes))
                data = np.unpackbits(data, axis=1)
                data = np.where(data != 0, 255, 0).astype(uint8)

                self._glyphs[int(cp, base=16)] = data

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

    def parse_image(self, image: ndarray) -> str:
        # image = np.where(image == 0, 255, 0).astype(uint8)
        best = (0, 100)
        for code, glyph in self._glyphs.items():
            glyph = np.where(glyph == 1, 255, 0).astype(uint8)

            glyph_cont, _ = cv.findContours(glyph, 2, 1)
            img_cont, _ = cv.findContours(image, 2, 1)

            try:
                c1 = glyph_cont[0]
                c2 = img_cont[0]
                match = cv.matchShapes(c1, c2, 1, 0.0)
                if match < best[1]:
                    best = (code, match)
                # print(f'{chr(code)}: {match}')
            except:
                pass

        # cv.imshow('img', image)
        # cv.imshow('best match', self._glyphs[best[0]])
        # cv.waitKey()
        # print(f'Best match: {chr(best[0])} - {best[1]}')
        return chr(best[0])


@dataclass
class ParsedCharacter:
    image: NDArray[uint8]
    matches: list[str]
    match_values: list[float]

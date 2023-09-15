from dataclasses import dataclass

import numpy as np
from numpy import uint8
from numpy.typing import NDArray

from print_mech_analyser.printout import Printout
from print_mech_analyser.font import Font, CharMatch


def split_lines(image: NDArray[uint8], font: Font) -> list[NDArray[uint8]]:
    # Index the rowss that have something in them.
    burned_rows = np.any(image, axis=1)
    in_whitespace: bool = not burned_rows[0]

    chunks: list[NDArray[uint8]] = []
    chunk_start: int = 0

    for col_ptr, burned_col in enumerate(burned_rows):
        # Every time we switch from a whitespace to a burned row or vice versa, split a
        # chunk off.
        if burned_col and in_whitespace:
            # A chunk of whitespace (may consist of more than one row)
            chunk = image[chunk_start:col_ptr, :]

            in_whitespace = False
            chunk_start = col_ptr

            # Don't include inter-row whitespace.
            if chunk.shape[0] >= font.glyph_height:
                chunks.append(chunk)

            continue

        if (not burned_col) and (not in_whitespace):
            # We have a chunk of 'something' (may be one or more characters or graphics)
            chunks.append(image[chunk_start:col_ptr, :])
            in_whitespace = True
            chunk_start = col_ptr
            continue

    # Apend the last chunk
    chunks.append(image[chunk_start:, :])

    return chunks


# Split a line into chunks of alternating whitespace and characters.
def split_line_characters(line: NDArray[uint8], font: Font) -> list[NDArray[uint8]]:
    # Index the columns that have something in them.
    burned_cols = np.any(line, axis=0)

    in_whitespace: bool = not burned_cols[0]
    chunks: list[NDArray[uint8]] = []
    chunk_start: int = 0

    for col_ptr, burned_col in enumerate(burned_cols):
        # Every time we switch from a whitespace to a burned column or vice versa, split
        # a chunk off.
        if burned_col and in_whitespace:
            # A chunk of whitespace (may consist of more than one character)
            chunk = line[:, chunk_start:col_ptr]

            in_whitespace = False
            chunk_start = col_ptr

            # Don't include inter-character whitespace.
            if chunk.shape[1] >= font.glyph_width:
                chunks.append(chunk)

            continue

        if (not burned_col) and (not in_whitespace):
            # We have a chunk of 'something' (may be one or more characters or graphics)
            chunks.append(line[:, chunk_start:col_ptr])
            in_whitespace = True
            chunk_start = col_ptr
            continue

    # Apend the last chunk
    chunks.append(line[:, chunk_start:])

    return chunks


def parse_char(char: NDArray[uint8], fonts: list[Font]) -> list[CharMatch] | None:
    matches: list[CharMatch] = []
    for font in fonts:
        matches.extend(font.parse_image(char))

    if len(matches) == 0:
        return None

    matches.sort(key=lambda m: m.match)
    return matches


def parse_line(line: NDArray[uint8], fonts: list[Font]) -> list[list[CharMatch] | None]:
    chars = split_line_characters(line, fonts[0])
    return [parse_char(char, fonts) for char in chars]


def parse_printout(
    printout: Printout, fonts: list[Font]
) -> list[list[list[CharMatch] | None]]:
    lines = split_lines(np.array(printout), fonts[0])
    return [parse_line(line, fonts) for line in lines]


################################


@dataclass
class HorizontalSpace:
    beg: int
    end: int

    @property
    def len(self) -> int:
        return self.end - self.beg


@dataclass
class WhiteSpace(HorizontalSpace):
    pass


@dataclass
class UnknownSpace(HorizontalSpace):
    pass


# Contains possible matches.
# beg & end may contradict the parent space.
# Confirmed matches can be used to constrain the parent space.
# Have position be part of the charmatch!
@dataclass
class CharSpace(HorizontalSpace):
    matches: list[CharMatch]


################################


@dataclass
class VerticalSpace:
    beg: int
    end: int

    contents: list[HorizontalSpace]

    @property
    def len(self) -> int:
        return self.end - self.beg


################################


def parse_space(printout: Printout) -> list[VerticalSpace]:
    burned_rows: NDArray = np.any(printout, axis=1)

    offsets = np.where(burned_rows[:-1] != burned_rows[1:])[0] + 1
    offsets = np.insert(offsets, 0, 0)

    vertical_spaces: list[VerticalSpace] = []
    for i in range(0, len(offsets)):
        beg: int = offsets[i]
        end: int = offsets[i + 1] if (i + 1) < len(offsets) else printout.length

        vertical_spaces.append(
            VerticalSpace(
                beg=beg,
                end=end,
                contents=parse_horizontal_space(printout[beg:end, :]),
            )
        )

    return vertical_spaces


def parse_horizontal_space(printout: Printout) -> list[HorizontalSpace]:
    burned_cols: NDArray = np.any(printout, axis=0)

    offsets = np.where(burned_cols[:-1] != burned_cols[1:])[0] + 1
    offsets = np.insert(offsets, 0, 0)

    chunks: list[HorizontalSpace] = []

    for i in range(0, len(offsets)):
        beg: int = offsets[i]
        end: int = offsets[i + 1] if (i + 1) < len(offsets) else printout.width

        if burned_cols[beg]:
            chunks.append(UnknownSpace(beg, end))
        else:
            chunks.append(WhiteSpace(beg, end))

    return chunks

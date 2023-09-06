import numpy as np
from numpy import uint8
from numpy.typing import NDArray

from print_mech_analyser.printout import Printout
from print_mech_analyser.font import Font, CharMatch


def split_lines(printout: Printout, font: Font) -> list[NDArray[uint8]]:
    non_zero_rows = np.any(printout, axis=1)

    lines: list[NDArray[uint8]] = []
    line: bool = False
    start_row = 0
    for i, non_zero in enumerate(non_zero_rows):
        if non_zero and not line:
            start_row = i
            line = True
        if not non_zero and line:
            lines.append(printout[start_row:i, :]._img)
            line = False

    return lines


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
            if chunk.shape[1] < font.glyph_width:
                continue

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


def parse_char(char: NDArray[uint8], font: Font) -> list[CharMatch] | None:
    matches = font.parse_image(char)
    if len(matches) == 0:
        return None

    matches.sort(key=lambda m: m.match)
    return matches


def parse_line(line: NDArray[uint8], font: Font) -> list[list[CharMatch] | None]:
    chars = split_line_characters(line, font)
    return [parse_char(char, font) for char in chars]


def parse_printout(
    printout: Printout, font: Font
) -> list[list[list[CharMatch] | None]]:
    lines = split_lines(printout, font)
    return [parse_line(line, font) for line in lines]

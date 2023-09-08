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

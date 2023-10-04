from dataclasses import dataclass
from typing import SupportsIndex

import numpy as np
from numpy.typing import NDArray

from print_mech_analyser.printout import Printout
from print_mech_analyser.parse.glyph import GlyphMatch
from print_mech_analyser.geometry import BoundingBox, Point, Span


################################


@dataclass(slots=True)
class HorizontalSpace:
    """
    Description
    -----------
    Type describing a horizontal span of space with no defined content.

    """

    span: Span

    def __len__(self) -> int:
        return len(self.span)

    @property
    def has_volume(self) -> bool:
        return self.span.end > self.span.beg

    @property
    def slice(self) -> slice:
        return self.span.slice

    def as_dict(self) -> dict[str, int]:
        return {
            "beg": int(self.span.beg),
            "end": int(self.span.end),
        }


@dataclass(slots=True)
class WhiteSpace(HorizontalSpace):
    """
    Description
    -----------
    Type describing a horizontal span of space containing no content.

    """

    pass


@dataclass(slots=True)
class UnknownSpace(HorizontalSpace):
    """
    Description
    -----------
    Type describing a horizontal span of space containing some unknown content.

    """

    pass


@dataclass(slots=True)
class GlyphSpace(HorizontalSpace):
    """
    Description
    -----------
    Type describing a horizontal span of space containing a known glyph or set of
    possible glyphs.

    """

    matches: list[GlyphMatch]

    def as_dict(self) -> dict[str, int | list[dict]]:
        return {
            "beg": int(self.span.beg),
            "end": int(self.span.end),
            "matches": [match.as_dict() for match in self.matches],
        }


################################


@dataclass(slots=True)
class VerticalSpace:
    """
    Description
    -----------
    Type describing a vertical span of space with a number horizontal descriptors
    describing it's contents.

    """

    span: Span
    contents: list[HorizontalSpace]

    def __getitem__(self, index: SupportsIndex) -> HorizontalSpace:
        return self.contents[index]

    def __setitem__(self, index: SupportsIndex, value: HorizontalSpace) -> None:
        self.contents[index] = value

    def __len__(self) -> int:
        return len(self.span)

    @property
    def is_whitespace(self) -> bool:
        return all(type(c) is WhiteSpace for c in self.contents)

    @property
    def has_volume(self) -> bool:
        return len(self.span) > 0

    @property
    def slice(self) -> slice:
        return self.span.slice

    def get_bbox(self, index: int) -> BoundingBox:
        """
        Description
        -----------
        Get the bounding box for the space at the given index.

        """
        return BoundingBox(
            Point(self.contents[index].span.beg, self.span.beg),
            Point(self.contents[index].span.end, self.span.end),
        )

    def as_dict(self) -> dict[str, int | list[dict]]:
        return {
            "beg": int(self.span.beg),
            "end": int(self.span.end),
            "content": [hs.as_dict() for hs in self.contents],
        }


################################


def from_printout(printout: Printout, roi: Span | None = None) -> list[VerticalSpace]:
    """
    Description
    -----------
    Parse a printout into into a list of descriptors describing distinct regions of
    space. Parsing is done line by line, top to bottom, left to right.

    Parameters
    ----------
    printout: Printout
        Printout to parse.

    roi: Span
        Vertical slice of the printout to operate on.

    Returns
    -------
    list[VerticalSpace]
        List of descriptors.

    """
    print = printout if roi is None else printout[roi.slice]
    roi_offset = 0 if roi is None else roi.beg

    burned_rows: NDArray = np.any(print, axis=1)

    offsets = np.where(burned_rows[:-1] != burned_rows[1:])[0] + 1
    offsets = np.insert(offsets, 0, 0)

    vertical_spaces: list[VerticalSpace] = []
    for i in range(0, len(offsets)):
        beg: int = offsets[i]
        end: int = offsets[i + 1] if (i + 1) < len(offsets) else print.length

        vertical_spaces.append(
            VerticalSpace(
                span=Span(beg + roi_offset, end + roi_offset),
                contents=parse_horizontal(print[beg:end, :]),
            )
        )

    return vertical_spaces


def parse_horizontal(printout: Printout) -> list[HorizontalSpace]:
    burned_cols: NDArray = np.any(printout, axis=0)

    offsets = np.where(burned_cols[:-1] != burned_cols[1:])[0] + 1
    offsets = np.insert(offsets, 0, 0)

    spans = [Span(beg, end) for beg, end in zip(offsets[:-1], offsets[1:])]
    spans.append(Span(offsets[-1], printout.width))

    return [UnknownSpace(s) if burned_cols[s.beg] else WhiteSpace(s) for s in spans]

from dataclasses import dataclass
from typing import Final, Self, SupportsIndex

import numpy as np
from numpy.typing import NDArray

from print_mech_analyser.printout import Printout
from print_mech_analyser.font import Font
from print_mech_analyser.parse.character import parse_image_character_bbox, CharMatch
from print_mech_analyser.geometry import BoundingBox, Point, Span


################################


@dataclass
class HorizontalSpace:
    span: Span

    def __len__(self) -> int:
        return len(self.span)

    @property
    def has_volume(self) -> bool:
        return len(self.span) > 0

    @property
    def slice(self) -> slice:
        return self.span.slice

    def as_dict(self) -> dict[str, int]:
        return {
            "beg": int(self.span.beg),
            "end": int(self.span.end),
        }


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

    def as_dict(self) -> dict[str, int | list[dict]]:
        return {
            "beg": int(self.span.beg),
            "end": int(self.span.end),
            "matches": [match.as_dict() for match in self.matches],
        }


################################


@dataclass
class VerticalSpace:
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


@dataclass
class PrintoutDescriptor:
    printout: Printout
    contents: list[VerticalSpace]
    fonts: list[Font]

    @classmethod
    def new(cls, printout: Printout, fonts: list[Font]) -> Self:
        space = parse_space(printout)
        space = parse_unknown(printout, space, fonts)
        space = constrain(space)
        self = cls(printout, space, fonts)

        return self

    def extend(self, extension: Printout) -> None:
        self.printout.extend(extension)

        new_slice_roi = Span(
            self.contents[-1].span.beg,
            self.contents[-1].span.end + extension.length,
        )

        self.contents = self.contents[:-1]

        # Need to offset the new space.
        space = parse_space(self.printout, roi=new_slice_roi)
        space = parse_unknown(self.printout, space, self.fonts)
        space = constrain(space)
        self.contents.extend(space)

    def as_dict(self) -> dict[str, list[dict]]:
        return {"fonts": [], "content": [vs.as_dict() for vs in self.contents]}


################################


def parse_space(printout: Printout, roi: Span | None = None) -> list[VerticalSpace]:
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
                contents=parse_horizontal_space(print[beg:end, :]),
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
            chunks.append(UnknownSpace(Span(beg, end)))
        else:
            chunks.append(WhiteSpace(Span(beg, end)))

    return chunks


def parse_unknown(
    printout: Printout,
    space: list[VerticalSpace],
    fonts: list[Font],
) -> list[VerticalSpace]:
    result = space.copy()

    for y, vert in enumerate(space):
        horispaces = enumerate(vert.contents)
        unknownspaces = [(x, hs) for x, hs in horispaces if type(hs) is UnknownSpace]

        for x, hori in unknownspaces:
            bbox: Final = vert.get_bbox(x)

            matches: list[CharMatch] = []
            for font in fonts:
                # If the object is significantly bigger than a glyph, skip it.
                if len(vert) > (font.height * 1.5) or len(hori) > (font.width * 1.5):
                    continue

                matches.extend(
                    parse_image_character_bbox(np.array(printout), bbox, font)
                )

            if len(matches) == 0:
                continue

            matches.sort(key=lambda m: m.match)
            result[y][x] = CharSpace(hori.span, matches)

    return result


def constrain(space: list[VerticalSpace]) -> list[VerticalSpace]:
    result = space.copy()

    for y, vert in enumerate(space):
        vert_spans: list[Span] = []

        horispaces = enumerate(vert.contents)
        horispaces = [(x, hor) for x, hor in horispaces if type(hor) is CharSpace]
        horispaces = [(x, hor) for x, hor in horispaces if hor.matches[0].match < 0.001]

        for x, hori in horispaces:
            # Constrain the space.
            match_hori_span = hori.matches[0].pos.horizontal_span
            match_vert_span = hori.matches[0].pos.vertical_span

            result[y][x].span = match_hori_span

            # Constrain adjascent space.
            if x > 0:
                result[y][x - 1].span.end = match_hori_span.beg

            if x < (len(vert.contents) - 1):
                result[y][x + 1].span.beg = match_hori_span.end

            vert_spans.append(match_vert_span)

        # Constrain the vertical space.
        if len(vert_spans) == 0:
            continue

        if all(span == vert_spans[0] for span in vert_spans[1:]):
            result[y].span = vert_spans[0]

            # Constrain adjascent space.
            if y > 0:
                result[y - 1].span.end = vert_spans[0].beg

            if y < (len(space) - 1):
                result[y + 1].span.beg = vert_spans[0].end

        # Filter any 0 sized horizontal space
        result[y].contents = [x for x in space[y].contents if x.has_volume]

    # Filter any 0 size vertical space.
    result = [y for y in space if y.has_volume]

    return result

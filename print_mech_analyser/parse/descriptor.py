from dataclasses import dataclass
from typing import Final, Self

import numpy as np

import print_mech_analyser.parse.space as parse_space
import print_mech_analyser.parse.glyph as parse_glyph
from print_mech_analyser.printout import Printout
from print_mech_analyser.font import Font
from print_mech_analyser.geometry import Span
from print_mech_analyser.parse.glyph import GlyphMatch
from print_mech_analyser.parse.space import VerticalSpace, UnknownSpace, GlyphSpace

################################


@dataclass(slots=True)
class PrintoutDescriptor:
    printout: Printout
    contents: list[VerticalSpace]
    fonts: list[Font]

    @classmethod
    def new(cls, printout: Printout, fonts: list[Font]) -> Self:
        space: list[VerticalSpace] = parse_space.from_printout(printout)
        space = parse_unknown(printout, space, fonts)
        space = constrain_whitespace(space)
        self = cls(printout, space, fonts)

        return self

    def extend(self, extension: Printout) -> None:
        self.printout.extend(extension)

        new_slice_roi = Span(
            self.contents[-1].span.beg,
            self.printout.length,
        )

        self.contents = self.contents[:-1]

        # Need to offset the new space.
        space = parse_space.from_printout(self.printout, roi=new_slice_roi)
        space = parse_unknown(self.printout, space, self.fonts)
        space = constrain_whitespace(space)
        self.contents.extend(space)

    def as_dict(self) -> dict[str, list[dict]]:
        return {"fonts": [], "content": [vs.as_dict() for vs in self.contents]}


################################


def parse_unknown(
    printout: Printout,
    space: list[VerticalSpace],
    fonts: list[Font],
) -> list[VerticalSpace]:
    result: list[VerticalSpace] = space.copy()

    for y, vert in enumerate(space):
        horispaces = enumerate(vert.contents)
        unknownspaces = [(x, hs) for x, hs in horispaces if type(hs) is UnknownSpace]

        for x, hori in unknownspaces:
            bbox: Final = vert.get_bbox(x)

            matches: list[GlyphMatch] = []
            for font in fonts:
                # If the object is significantly bigger than a glyph, skip it.
                if len(vert) > (font.height * 1.5) or len(hori) > (font.width * 1.5):
                    continue

                matches.extend(parse_glyph.from_image(np.array(printout), bbox, font))

            if len(matches) == 0:
                continue

            matches.sort(key=lambda m: m.match)
            result[y][x] = GlyphSpace(hori.span, matches)

    return result


def constrain_whitespace(space: list[VerticalSpace]) -> list[VerticalSpace]:
    result: list[VerticalSpace] = space.copy()

    for y, vert in enumerate(space):
        vert_spans: list[Span] = []

        horispaces = enumerate(vert.contents)
        horispaces = [(x, hor) for x, hor in horispaces if type(hor) is GlyphSpace]
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

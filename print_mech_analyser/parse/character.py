from dataclasses import dataclass
import math
from typing import Final, Sequence
from functools import partial

import numpy as np
from numpy import uint8
from numpy.typing import NDArray

import cvlog
import cv2 as cv

from print_mech_analyser.font import Font
from print_mech_analyser.geometry import BoundingBox, Point

TEMPLATE_THRESHOLD: Final[float] = 100
CONTOUR_THRESHOLD: Final[float] = 0.1


@dataclass
class CharMatch:
    char: str
    font: str
    code_point: int
    match: float
    pos: BoundingBox


def parse_image_character_bbox(
    image: NDArray[uint8], bbox: BoundingBox, font: Font
) -> list[CharMatch]:
    """
    Description
    -----------
    Parse a character in an image.

    """
    # Pad the image if nescessary.
    xpad: Final[int] = font.width - bbox.width if bbox.width < font.width else 0
    ypad: Final[int] = font.height - bbox.height if bbox.height < font.height else 0

    image_bbox: Final = BoundingBox(Point(0, 0), Point(image.shape[1], image.shape[0]))
    bbox_padded: Final = BoundingBox(
        bbox.p1 - Point(xpad, ypad),
        bbox.p2 + Point(xpad, ypad),
    ).clamp(image_bbox)

    character: Final[NDArray[uint8]] = image[bbox_padded.slice]

    cvlog.image(cvlog.Level.INFO, character)

    # If image is whitespace whitespace.
    # TODO return list of possible whitespace chars instead.
    if not np.any(character):
        spaces = math.floor(image.shape[1] / font.width)
        return [
            CharMatch(
                char="".join([" " for _ in range(spaces)]),
                font=font.name,
                code_point=0x20,
                match=0.0,
                pos=BoundingBox(Point(0, 0), Point(0, 0)),
            )
        ]

    image_contrs = cv.findContours(
        image[bbox.slice], cv.RETR_LIST, cv.CHAIN_APPROX_NONE
    )[0]

    # Find a set of matches using the relatively fast contour matching technique.
    # Contour matching is scale and rotation invariant so may give some false
    # positives.
    match_contrs = partial(contour_similarity, image_contrs)

    matches = zip(font.code_points, font.glyphs, font.contours)
    matches = [m for m in matches if len(m[2]) != 0]
    matches = [m + (match_contrs(m[2]),) for m in matches]
    matches = [m for m in matches if m[3] < CONTOUR_THRESHOLD]

    # Refine the match set using template matching.
    match_temp = partial(template_similarity, character)

    matches = [m + (match_temp(m[1]),) for m in matches]
    matches = [m for m in matches if m[4][0] < TEMPLATE_THRESHOLD]

    ########

    result_width: int = bbox_padded.width - font.width + 1
    result_height: int = bbox_padded.height - font.height + 1

    ########

    char_matches: list[CharMatch] = []
    for cp, _, _, match_cont, match_temp in matches:
        match_top_left: Point = Point(match_temp[1][0], match_temp[1][1])
        match_center: Point = Point(
            match_top_left.x + int(result_width / 2),
            match_top_left.y + int(result_height / 2),
        )

        # Translate from coords in the padded image to coords in the bbox image.
        transform_vector = Point(
            bbox.p1.x - bbox_padded.p1.x, bbox.p1.y - bbox_padded.p1.y
        )

        match_center = match_center - transform_vector

        # Translate form the bbox image to the main image.
        match_center = bbox_padded.center + match_center

        corner_offset = Point(
            int(font.width / 2),
            int(font.height / 2),
        )

        p1 = match_center - corner_offset
        p2 = match_center + corner_offset

        char_matches.append(
            CharMatch(
                char=chr(cp),
                font=font.name,
                code_point=cp,
                match=match_temp[0],
                pos=BoundingBox(p1, p2).clamp(image_bbox),
            )
        )

    return char_matches


def contour_similarity(contours1: Sequence, contours2: Sequence) -> float:
    """
    Description
    -----------
    Find a set of matches using the relatively fast contour matching technique.
    Contour matching is scale and rotation invariant so may give some false positives.

    """

    def match_contour(c1, c2) -> float:
        return cv.matchShapes(c1, c2, cv.CONTOURS_MATCH_I1, 0.0)

    if len(contours1) == 0 or len(contours2) == 0:
        return 0

    match_sum = sum(match_contour(c1, c2) for c1, c2 in zip(contours1, contours2))
    return match_sum / len(contours1)


def template_similarity(
    template: NDArray[uint8], image: NDArray[uint8]
) -> tuple[float, tuple[int, int]]:
    result = cv.matchTemplate(image, template, cv.TM_SQDIFF)
    min, _, pos, _ = cv.minMaxLoc(result)

    # cvlog.image(cvlog.Level.INFO, result, msg=f"score: {min}, position: {pos}")
    return min, pos

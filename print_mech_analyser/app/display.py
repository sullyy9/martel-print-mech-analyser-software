from pathlib import Path
import tkinter
from tkinter import Canvas, PhotoImage, Frame, Scrollbar, Event, Text
from typing import Final
from idlelib.tooltip import Hovertip

import numpy as np
from numpy import uint8
from numpy.typing import NDArray

from print_mech_analyser.printout import Printout
from print_mech_analyser.pretty_printout import PrettyPrintout
from print_mech_analyser.font import Font
from print_mech_analyser.parse import PrintoutDescriptor
from print_mech_analyser.parse.character import CharMatch
from print_mech_analyser.parse.parse import WhiteSpace, UnknownSpace, CharSpace
from print_mech_analyser.geometry import BoundingBox, Point

# Tkinter uses RGB, not BGR.
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
TEAL = (0, 255, 255)

SPACE_CHAR: Final = CharMatch(" ", "?", 0x20, 0, BoundingBox(Point(0, 0), Point(0, 0)))
UNKNOWN: Final = CharMatch("�", "?", 0x20, 0, BoundingBox(Point(0, 0), Point(0, 0)))


def ndarray_to_photo_image(array: NDArray[uint8]) -> PhotoImage:
    if len(array.shape) == 2:
        height, width = array.shape
        data = f"P5 {width} {height} 255 ".encode() + array.tobytes()
    else:
        height, width, _ = array.shape
        data = f"P6 {width} {height} 255 ".encode() + array.tobytes()

    return PhotoImage(width=width, height=height, data=data, format="PPM")


def color_printout(printout: Printout, desc: PrintoutDescriptor) -> PrettyPrintout:
    pretty = PrettyPrintout.from_printout(printout)

    vertspace = desc.contents
    white_vertspace = [vs for vs in vertspace if vs.is_whitespace]
    object_vertspace = [vs for vs in vertspace if (not vs.is_whitespace)]

    [pretty.highlight_strip(vs.span, YELLOW) for vs in white_vertspace]

    for vs in object_vertspace:
        horispace = [(hs, vs.get_bbox(i)) for i, hs in enumerate(vs.contents)]

        whitespace = [bbox for hs, bbox in horispace if type(hs) is WhiteSpace]
        unknownspace = [bbox for hs, bbox in horispace if type(hs) is UnknownSpace]
        charspace = [bbox for hs, bbox in horispace if type(hs) is CharSpace]

        [pretty.highlight_area(bbox, TEAL) for bbox in whitespace]
        [pretty.highlight_area(bbox, RED) for bbox in unknownspace]

        [pretty.highlight_area(bbox, BLUE) for bbox in charspace[0::2]]
        [pretty.highlight_area(bbox, GREEN) for bbox in charspace[1::2]]

    return pretty


class Display(Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master=master, **kw)

        self._print = PrintDisplay(self, borderwidth=5, relief=tkinter.GROOVE)
        self._text = TextDisplay(self)
        self._scroll: Final = Scrollbar(self, orient="vertical", width=16)

        self._descriptor: PrintoutDescriptor | None = None
        self._fonts: list[Font] = []

        self._print.grid(row=0, column=0, sticky="nsew")
        self._text.grid(row=0, column=1, sticky="nsew")
        self._scroll.grid(row=0, column=2, sticky="nsew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1, minsize=384)
        self.grid_columnconfigure(1, weight=1, minsize=384)
        self.grid_columnconfigure(2, weight=0, minsize=10)

        self._print.set_scrollbar(self._scroll)
        self._text.set_scrollbar(self._scroll)
        self._scroll.config(command=self.yview)

        self.bind_class(str(self._print._canvas), "<MouseWheel>", self.scroll)
        self.bind_class(str(self._text._text_box), "<MouseWheel>", self.scroll)

    def set_fonts(self, fonts: list[Font]) -> None:
        self._fonts = fonts

    def append(self, printout: Printout) -> None:
        if self._descriptor is None:
            self.set(printout)
            return

        self.clear()
        self._descriptor.extend(printout)

        pretty = color_printout(self._descriptor.printout, self._descriptor)
        for vs in self._descriptor.contents:
            for hs in vs.contents:
                match hs:
                    case WhiteSpace():
                        self._text.append_character([SPACE_CHAR], 16)
                    case CharSpace():
                        self._text.append_character(hs.matches, 16)
                    case UnknownSpace():
                        self._text.append_character([UNKNOWN], 8)

            self._text.new_line()

        self._print.set(pretty)

    def set(self, printout: Printout) -> None:
        self.clear()
        self._descriptor = PrintoutDescriptor.new(printout, self._fonts)

        pretty = color_printout(printout, self._descriptor)
        for vs in self._descriptor.contents:
            for hs in vs.contents:
                match hs:
                    case WhiteSpace():
                        self._text.append_character([SPACE_CHAR], 16)
                    case CharSpace():
                        self._text.append_character(hs.matches, 16)
                    case UnknownSpace():
                        self._text.append_character([UNKNOWN], 8)

            self._text.new_line()

        self._print.set(pretty)

        pretty.save(Path("parsed.png"))

    def clear(self) -> None:
        self._print.clear()
        self._text.clear()

    def get_printout(self) -> Printout | None:
        return self._print.get_printout()

    def yview(self, *args):
        self._print.yview(*args)
        self._text.yview(*args)

    def scroll(self, event: Event):
        self._print.scroll(event)
        self._text.scroll(event)


class PrintDisplay(Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master=master, **kw)

        self._canvas: Final = Canvas(self, highlightthickness=0)
        self._image: NDArray[uint8] | None = None
        self._photo_image: PhotoImage | None = None
        self._canvas_image = self._canvas.create_image(0, 0, anchor="nw", image=None)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._canvas.grid(row=0, column=0, sticky="ns")

    def append(self, printout: Printout) -> None:
        if self._image is None:
            self.set(printout)
            return

        self._image = np.vstack((self._image, printout))

        self._photo_image = ndarray_to_photo_image(self._image)

        self._canvas.itemconfig(self._canvas_image, image=self._photo_image)
        self._canvas.config(scrollregion=self._canvas.bbox("all"))

    def set(self, printout: Printout | PrettyPrintout) -> None:
        self._image = np.array(printout, dtype=uint8)

        self._photo_image = ndarray_to_photo_image(self._image)

        self._canvas.itemconfig(self._canvas_image, image=self._photo_image)
        self._canvas.config(scrollregion=self._canvas.bbox("all"))

    def clear(self) -> None:
        self._canvas.delete("all")
        self._image = None
        self._photo_image = None
        self._canvas_image = self._canvas.create_image(0, 0, anchor="nw", image=None)
        self._canvas.config(scrollregion=self._canvas.bbox("all"))

    def get_printout(self) -> Printout | None:
        return Printout(self._image) if self._image is not None else None

    def set_scrollbar(self, scrollbar: Scrollbar) -> None:
        self._canvas.config(yscrollcommand=scrollbar.set)

    def yview(self, *args) -> None:
        self._canvas.yview(*args)

    def scroll(self, event: Event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")  # For windows


class TextDisplay(Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master=master, **kw)

        self._text: list[list[CharMatch] | None] = []
        self._text_box: Final = Text(self)
        self._tooltip: ToolTip = ToolTip(self, "")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._text_box.grid(row=0, column=0, sticky="nsew")

    def append_character(self, char: list[CharMatch], size: int) -> None:
        char_index: Final[int] = len(self._text)
        tag: Final[str] = str(char_index)
        self._text.append(char)

        self._text_box.insert(tkinter.END, char[0].char, tag)
        self._text_box.tag_configure(tag, font=("Consolas", size))

        self._text_box.tag_bind(
            tag, "<Enter>", func=lambda _: self.hover_show(char_index)
        )

        self._text_box.tag_bind(tag, "<Leave>", func=lambda _: self.hover_hide())

    def append_unknown(self, size: int) -> None:
        tag: Final[str] = str(len(self._text))
        self._text.append(None)

        self._text_box.insert(tkinter.END, "�", tag)
        self._text_box.tag_configure(tag, font=("Consolas", int(size / 2)))

    def new_line(self) -> None:
        self._text_box.insert(tkinter.END, "\n")

    def clear(self) -> None:
        self._text_box.delete("1.0", tkinter.END)
        self._text.clear()

    def hover_show(self, index: int) -> None:
        hovered_text = self._text[index]
        if hovered_text is None:
            return

        match_count: int = 5 if len(hovered_text) >= 5 else len(hovered_text)

        text: str = ""
        for match in hovered_text[:match_count]:
            text += f"char: {match.char} | "
            text += f"code: U+{match.code_point:04X}  | "
            text += f"font: {match.font} | "
            text += f"rating: {match.match}\n"

        self._tooltip.text = text
        self._tooltip.showtip()

    def hover_hide(self) -> None:
        self._tooltip.hidetip()

    def set_scrollbar(self, scrollbar: Scrollbar) -> None:
        self._text_box.config(yscrollcommand=scrollbar.set)

    def yview(self, *args) -> None:
        self._text_box.yview(*args)

    def scroll(self, event: Event):
        self._text_box.yview_scroll(int(-1 * (event.delta / 120)), "units")


class ToolTip(Hovertip):
    def position_window(self):
        if self.tipwindow is None:
            return

        x = self.anchor_widget.winfo_pointerx() + 1
        y = self.anchor_widget.winfo_pointery() - 1
        self.tipwindow.wm_geometry(f"+{x}+{y}")

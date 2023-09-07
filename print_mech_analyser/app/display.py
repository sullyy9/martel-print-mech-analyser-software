import tkinter
from tkinter import Canvas, PhotoImage, Frame, Scrollbar, Event, Text
from typing import Final
from idlelib.tooltip import Hovertip

import numpy as np

from print_mech_analyser.font import CharMatch
from print_mech_analyser.printout import Printout


class Display(Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master=master, **kw)

        self._print = PrintDisplay(self)
        self._text = TextDisplay(self)
        self._scroll: Final = Scrollbar(self, orient="vertical", width=16)

        self._print.grid(row=0, column=0, sticky="nsew")
        self._text.grid(row=0, column=1, sticky="nsew")
        self._scroll.grid(row=0, column=2, sticky="nsew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1, minsize=384)
        self.grid_columnconfigure(1, weight=1, minsize=384)
        self.grid_columnconfigure(2, weight=0, minsize=10)

        self._print.set_scrollbar(self._scroll)
        self._text.set_scrollbar(self._scroll)

        self.bind_class(str(self._print._canvas), "<MouseWheel>", self.scroll)
        self.bind_class(str(self._text._text_box), "<MouseWheel>", self.scroll)

    def update(self, printout: Printout) -> None:
        self._print.update(printout)

    def clear(self) -> None:
        self._print.clear()
        self._text.clear()

    def scroll(self, event: Event):
        self._print.scroll(event)
        self._text.scroll(event)


class PrintDisplay(Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master=master, **kw)

        self._canvas: Final = Canvas(self, highlightthickness=0)
        self._image: PhotoImage | None = None
        self._canvas_image = self._canvas.create_image(0, 0, anchor="nw", image=None)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._canvas.grid(row=0, column=0, sticky="nsew")

    def update(self, printout: Printout) -> None:
        new_image = np.array(printout)

        height, width = new_image.shape
        data = f"P5 {width} {height} 255 ".encode() + new_image.tobytes()

        self._image = PhotoImage(width=width, height=height, data=data, format="PPM")

        self._canvas.itemconfig(self._canvas_image, image=self._image)
        self._canvas.config(scrollregion=self._canvas.bbox("all"))

    def clear(self) -> None:
        self._canvas.delete("all")
        self._canvas_image = self._canvas.create_image(0, 0, anchor="nw", image=None)
        self._canvas.config(scrollregion=self._canvas.bbox("all"))

    def set_scrollbar(self, scrollbar: Scrollbar) -> None:
        self._canvas.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._canvas.yview)

    def scroll(self, event: Event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")  # For windows


class TextDisplay(Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master=master, **kw)

        self._text: list[list[CharMatch]] = []
        self._text_box: Final = Text(self)
        self._tooltip: ToolTip = ToolTip(self, "")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._text_box.grid(row=0, column=0, sticky="nsew")

    def append_character(self, char: list[CharMatch], size: int) -> None:
        char_index: Final[int] = len(self._text)
        tag: Final[str] = str(char_index)
        self._text.append(char)

        self._text_box.insert(tkinter.END, self._text[-1][0].char, tag)
        self._text_box.tag_configure(tag, font=("Consolas", size))

        self._text_box.tag_bind(
            tag, "<Enter>", func=lambda _: self.hover_show(char_index)
        )

        self._text_box.tag_bind(tag, "<Leave>", func=lambda _: self.hover_hide())

    def new_line(self) -> None:
        self._text_box.insert(tkinter.END, "\n")

    def clear(self) -> None:
        self._text_box.delete("1.0", tkinter.END)
        self._text.clear()

    def hover_show(self, index: int) -> None:
        match_count: int = 5 if len(self._text[index]) >= 5 else len(self._text[index])

        text: str = ""
        for match in self._text[index][:match_count]:
            text += f"{match.char} - {match.match}\n"

        self._tooltip.text = text
        self._tooltip.showtip()

    def hover_hide(self) -> None:
        self._tooltip.hidetip()

    def set_scrollbar(self, scrollbar: Scrollbar) -> None:
        self._text_box.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self._text_box.yview)

    def scroll(self, event: Event):
        self._text_box.yview_scroll(int(-1 * (event.delta / 120)), "units")


class ToolTip(Hovertip):
    def position_window(self):
        if self.tipwindow is None:
            return

        x = self.anchor_widget.winfo_pointerx() + 1
        y = self.anchor_widget.winfo_pointery() - 1
        self.tipwindow.wm_geometry(f"+{x}+{y}")

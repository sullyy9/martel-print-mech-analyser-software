import functools
from pathlib import Path
import serial.tools.list_ports
from tkinter import Tk, Canvas, PhotoImage, Frame, Scrollbar, Event, Button, Menu, Text
from tkinter import filedialog
import tkinter
from typing import Final
from serial import Serial
from idlelib.tooltip import Hovertip

import numpy as np

from print_mech_analyser.analyser import MechAnalyser
from print_mech_analyser.printout import Printout
from print_mech_analyser.font import Font, CharMatch
from print_mech_analyser import parse


class Application:
    _REFRESH_RATE: Final[int] = 50

    def __init__(self) -> None:
        self._root: Final = Tk()
        self._menubar: Final = Menu(self._root)
        self._display: Final = Display(self._root, background="bisque")
        self._controls: Final = Controls(
            self._root, borderwidth=5, relief=tkinter.GROOVE
        )

        self._analyser: MechAnalyser | None = None
        self._font: Font = Font(Path("./fonts/Arial16.json"))

        self._root.title("Print Mech Analyser")

        # Setup the menu bar.
        self._portmenu = PortMenu()
        self._menubar.add_cascade(label="Select Port", menu=self._portmenu)
        self._menubar.add_command(label="Save", command=self.save_printout)
        self._menubar.add_command(label="Load", command=self.load_printout)
        self._menubar.add_command(label="Clear", command=self.clear_printout)

        self._root.bind(
            "<<port-selected>>",
            lambda _: self.select_analyser(self._portmenu.port),
        )

        self._root.config(menu=self._menubar)

        self._root.grid_rowconfigure(0, weight=0)
        self._root.grid_rowconfigure(1, weight=1)
        self._root.grid_columnconfigure(0, weight=0)
        self._root.grid_columnconfigure(1, weight=1)

        self._controls.grid(row=0, column=0, sticky="nsew")
        self._display.grid(row=0, column=1, sticky="nsew", rowspan=2)

        self._root.bind(
            "<<record-start>>",
            lambda _: self._analyser.start_capture() if self._analyser else ...,
        )
        self._root.bind(
            "<<record-stop>>",
            lambda _: self._analyser.stop_capture() if self._analyser else ...,
        )
        self._root.bind(
            "<<paper-in>>",
            lambda _: self._analyser.set_paper_in() if self._analyser else ...,
        )
        self._root.bind(
            "<<paper-out>>",
            lambda _: self._analyser.set_paper_out() if self._analyser else ...,
        )
        self._root.bind(
            "<<platen-in>>",
            lambda _: self._analyser.set_platen_in() if self._analyser else ...,
        )
        self._root.bind(
            "<<platen-out>>",
            lambda _: self._analyser.set_platen_out() if self._analyser else ...,
        )

        self.update_printout()

    def mainloop(self) -> None:
        self._root.mainloop()

    def select_analyser(self, port: str) -> None:
        self._analyser = MechAnalyser(Serial(port, baudrate=230400))

    def update_printout(self) -> None:
        self._root.after(self._REFRESH_RATE, self.update_printout)

        if self._analyser is not None:
            self._analyser.process()
            printout = self._analyser.get_printout()
            self._display.update(printout)

    def save_printout(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Save printout", filetypes=[("PNG", ".png")], defaultextension=".*"
        )
        if filename is not None and self._analyser is not None:
            self._analyser.get_printout().save(Path(filename))

    def load_printout(self) -> None:
        filename = filedialog.askopenfilename(
            title="Load printout", filetypes=[("PNG", ".png")], defaultextension=".*"
        )

        if filename is not None and len(filename) > 0:
            printout = Printout.from_file(Path(filename))
            self._display.update(printout)

            for line in parse.parse_printout(printout, self._font):
                line_text: str = ""
                for char in line:
                    if char is not None:
                        self._display._text.append_character(char, 16)

                    line_text += char[0].char if char else "�"

                line_text += "\n"
                self._display._text.new_line()

    def clear_printout(self) -> None:
        self._display.clear()
        self._display.clear()


class PortMenu(Menu):
    def __init__(self, master=None, **kw) -> None:
        super().__init__(master=master, postcommand=self.refresh, **kw)
        self.port: str = ""

    def refresh(self) -> None:
        self.delete(0, "end")

        ports = [port.name for port in serial.tools.list_ports.comports()]

        for port in ports:
            self.add_radiobutton(
                label=port, command=functools.partial(self.port_selected, port)
            )

    def port_selected(self, port: str) -> None:
        self.port = port
        self.master.event_generate("<<port-selected>>")


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
        self._text_box.delete("all")
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

        x = self.anchor_widget.winfo_pointerx()
        y = self.anchor_widget.winfo_pointery()
        self.tipwindow.wm_geometry(f"+{x}+{y}")


class Controls(Frame):
    def __init__(self, master: Tk, **kw):
        super().__init__(master=master, **kw)

        self._record: Final = Button(self, width=15)
        self._paper: Final = Button(self, width=15)
        self._platen: Final = Button(self, width=15)

        self._recording: bool = False
        self._paper_in: bool = False
        self._platen_in: bool = False

        self._record.grid(row=0, column=0, padx=2, pady=2)
        self._paper.grid(row=1, column=0, padx=2, pady=2)
        self._platen.grid(row=1, column=1, padx=2, pady=2)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._record.config(text="Start Recording", command=self.record_click)
        self._paper.config(text="Toggle Paper", command=self.paper_toggle_click)
        self._platen.config(text="Toggle Platen", command=self.platen_toggle_click)

    def record_click(self) -> None:
        event = "<<record-stop>>" if self._recording else "<<record-start>>"
        text = "Start Recording" if self._recording else "Stop Recording"

        self.master.event_generate(event)
        self._record.config(text=text, command=self.record_click)
        self._recording = not self._recording

    def paper_toggle_click(self) -> None:
        event = "<<paper-out>>" if self._paper_in else "<<paper-in>>"
        self.master.event_generate(event)
        self._paper_in = not self._paper_in

    def platen_toggle_click(self) -> None:
        event = "<<platen-out>>" if self._platen_in else "<<platen-in>>"
        self.master.event_generate(event)
        self._platen_in = not self._platen_in


if __name__ == "__main__":
    app = Application()
    app.mainloop()

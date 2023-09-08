from pathlib import Path
from tkinter import Tk, Menu
from tkinter import filedialog
import tkinter
from typing import Final
from serial import Serial

from print_mech_analyser.analyser import MechAnalyser
from print_mech_analyser.printout import Printout
from print_mech_analyser.font import Font
from print_mech_analyser import parse

from print_mech_analyser.app.display import Display
from print_mech_analyser.app.controls import Controls, PortMenu


class App:
    _REFRESH_RATE: Final[int] = 50

    def __init__(self) -> None:
        self._root: Final = Tk()
        self._menubar: Final = Menu(self._root)
        self._display: Final = Display(self._root)
        self._controls: Final = Controls(
            self._root, borderwidth=5, relief=tkinter.GROOVE
        )

        self._analyser: MechAnalyser | None = None

        arial16 = Font.from_json(Path("./fonts/Arial16.json"))
        self._fonts: list[Font] = [arial16, arial16.into_bold()]

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
            # printout = self._analyser.get_printout()
            # self._display.set(printout)
            printout = self._analyser.take_printout()
            if printout is not None:
                self._display.append(printout)

    def save_printout(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Save printout", filetypes=[("PNG", ".png")], defaultextension=".*"
        )
        if filename is not None:
            printout = self._display.get_printout()
            if printout is not None:
                printout.save(Path(filename))

    def load_printout(self) -> None:
        filename = filedialog.askopenfilename(
            title="Load printout", filetypes=[("PNG", ".png")], defaultextension=".*"
        )

        if filename is not None and len(filename) > 0:
            printout = Printout.from_file(Path(filename))
            self._display.set(printout)

            for line in parse.parse_printout(printout, self._fonts):
                for char in line:
                    if char is not None:
                        self._display._text.append_character(char, 16)

                self._display._text.new_line()

    def clear_printout(self) -> None:
        self._display.clear()

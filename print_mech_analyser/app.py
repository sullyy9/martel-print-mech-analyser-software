import functools
from pathlib import Path
import serial.tools.list_ports
from tkinter import Tk, Canvas, PhotoImage, Frame, Scrollbar, Event, Button, Menu
from tkinter import filedialog
import tkinter
from typing import Final, Optional
from serial import Serial


import numpy as np

from print_mech_analyser.analyser import MechAnalyser
from print_mech_analyser.printout import Printout


class Application:
    _REFRESH_RATE: Final[int] = 50

    def __init__(self) -> None:
        self._root: Final = Tk()
        self._menubar: Final = Menu(self._root)
        self._display: Final = PrintoutDisplay(self._root, background="bisque")
        self._controls: Final = Controls(
            self._root, borderwidth=5, relief=tkinter.GROOVE
        )

        self._analyser: MechAnalyser | None = None

        self._root.title("Print Mech Analyser")

        # Setup the menu bar.
        self._portmenu = PortMenu()
        self._menubar.add_cascade(label="Select Port", menu=self._portmenu)
        self._menubar.add_command(label="Save", command=self.save_printout)
        self._menubar.add_command(label="Load", command=self.load_printout)

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

            self._display.update_printout(printout)

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
            self._display.update_printout(printout)


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


class PrintoutDisplay(Frame):
    def __init__(self, master=None, printout: Optional[Printout] = None, **kw):
        super().__init__(master=master, **kw)

        self._canvas: Final = Canvas(self, highlightthickness=0)
        self._scroll: Final = Scrollbar(self, orient="vertical", width=10)
        self._image: PhotoImage | None = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._scroll.grid(row=0, column=1, sticky="ns")

        # Bind the mousewheel to canvas scroll control.
        self._canvas.config(yscrollcommand=self._scroll.set)
        self._canvas.config(scrollregion=self._canvas.bbox("all"))
        self._canvas.bind_class(str(self._canvas), "<MouseWheel>", self.mouse_scroll)
        self._scroll.config(command=self._canvas.yview)

        self.printout_container = self._canvas.create_image(
            0, 0, anchor="nw", image=None
        )

        if printout is not None:
            self.update_printout(printout)

    def update_printout(self, printout: Printout) -> None:
        new_image = np.array(printout)

        height, width = new_image.shape
        data = f"P5 {width} {height} 255 ".encode() + new_image.tobytes()
        self._image = PhotoImage(width=width, height=height, data=data, format="PPM")
        self._canvas.itemconfig(self.printout_container, image=self._image)
        self._canvas.config(scrollregion=self._canvas.bbox("all"))

    def mouse_scroll(self, event: Event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")  # For windows


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

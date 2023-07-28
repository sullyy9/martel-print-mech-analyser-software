from tkinter import Tk, Canvas, PhotoImage, Frame, Scrollbar, Event, Button
from typing import Final, Optional
from serial import Serial


import numpy as np

from print_mech_analyser.analyser import MechAnalyser
from print_mech_analyser.printout import Printout


class Application:
    _REFRESH_RATE: Final[int] = 50

    def __init__(self) -> None:
        self._root: Final = Tk()
        self._display: Final = PrintoutDisplay(self._root, background="bisque")
        self._controls: Final = Controls(self._root)

        self._analyser: MechAnalyser = MechAnalyser(Serial("COM18", baudrate=230400))

        self._root.title("Print Mech Analyser")

        self._root.grid_rowconfigure(0, weight=1)
        self._root.grid_columnconfigure(0, weight=1)

        self._controls.grid(row=0, column=0)
        self._display.grid(row=0, column=1, sticky="nsew", rowspan=2)

        self._root.bind("<<record-start>>", lambda _: self._analyser.start_capture())
        self._root.bind("<<record-stop>>", lambda _: self._analyser.stop_capture())
        self._root.bind("<<paper-in>>", lambda _: self._analyser.set_paper_in())
        self._root.bind("<<paper-out>>", lambda _: self._analyser.set_paper_out())
        self._root.bind("<<platen-in>>", lambda _: self._analyser.set_platen_in())
        self._root.bind("<<platen-out>>", lambda _: self._analyser.set_platen_out())

        self.update_printout()

    def mainloop(self) -> None:
        self._root.mainloop()

    def update_printout(self) -> None:
        self._root.after(self._REFRESH_RATE, self.update_printout)

        self._analyser.process()
        printout = self._analyser.get_printout()

        self._display.update_printout(printout)


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

        self._record: Final = Button()
        self._paper: Final = Button()
        self._platen: Final = Button()

        self._recording: bool = False
        self._paper_in: bool = False
        self._platen_in: bool = False

        self._record.grid(row=0, column=0)
        self._paper.grid(row=1, column=0)
        self._platen.grid(row=2, column=0)

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

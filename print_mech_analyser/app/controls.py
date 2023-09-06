import functools
import serial.tools.list_ports
from tkinter import Tk, Frame, Button, Menu
from typing import Final


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

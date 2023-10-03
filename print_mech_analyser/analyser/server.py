from enum import Enum, auto
from typing import Final, Self
from serial import Serial
from dataclasses import dataclass
from multiprocessing import Process, Queue

from print_mech_analyser.analyser.analyser import MechAnalyser
from print_mech_analyser.printout import Printout


class Request(Enum):
    EXIT = auto()

    SET_PAPER_IN = auto()
    SET_PAPER_OUT = auto()
    SET_PLATEN_IN = auto()
    SET_PLATEN_OUT = auto()

    RECORDING_START = auto()
    RECORDING_STOP = auto()

    PRINTOUT_GET = auto()
    PRINTOUT_TAKE = auto()


@dataclass()
class MechAnalyserServer:
    process: Process

    requests: Queue
    printout: Queue

    @classmethod
    def start(cls, serial: Serial) -> Self:
        requests: Queue = Queue()
        printout: Queue = Queue()

        process = Process(target=cls._run, args=[serial.name, requests, printout])
        process.start()

        return cls(process=process, requests=requests, printout=printout)

    def stop(self) -> None:
        self.requests.put(Request.EXIT)

    def kill(self) -> None:
        self.process.kill()

    def set_paper_in(self) -> None:
        self.requests.put(Request.SET_PAPER_IN)

    def set_paper_out(self) -> None:
        self.requests.put(Request.SET_PAPER_OUT)

    def set_platen_in(self) -> None:
        self.requests.put(Request.SET_PLATEN_IN)

    def set_platen_out(self) -> None:
        self.requests.put(Request.SET_PLATEN_OUT)

    def start_capture(self) -> None:
        self.requests.put(Request.RECORDING_START)

    def stop_capture(self) -> None:
        self.requests.put(Request.RECORDING_STOP)

    def get_printout(self) -> Printout | None:
        self.requests.put(Request.PRINTOUT_GET)
        return self.printout.get()

    def take_printout(self) -> Printout | None:
        self.requests.put(Request.PRINTOUT_TAKE)
        return self.printout.get()

    def clear_printout(self) -> None:
        self.requests.put(Request.PRINTOUT_TAKE)
        self.printout.get()

    @staticmethod
    def _run(port: str, requests: Queue, printout: Queue) -> None:
        analyser: Final = MechAnalyser(Serial(port, baudrate=230400))

        while True:
            analyser.process()

            if requests.empty():
                continue

            match (requests.get()):
                case Request.EXIT:
                    break
                case Request.SET_PAPER_IN:
                    analyser.set_paper_in()
                case Request.SET_PAPER_OUT:
                    analyser.set_paper_out()
                case Request.SET_PLATEN_IN:
                    analyser.set_platen_in()
                case Request.SET_PLATEN_OUT:
                    analyser.set_platen_out()
                case Request.RECORDING_START:
                    analyser.start_capture()
                case Request.RECORDING_STOP:
                    analyser.stop_capture()
                case Request.PRINTOUT_GET:
                    printout.put(analyser.get_printout())
                case Request.PRINTOUT_TAKE:
                    printout.put(analyser.take_printout())

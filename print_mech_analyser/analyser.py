from enum import Enum, IntEnum, auto
from typing import Final
from serial import Serial

import numpy as np
from numpy import uint8
from numpy.typing import NDArray

from .printout import Printout

HEAD_WIDTH: Final[int] = 384


class ByteCode(IntEnum):
    FRAME_START = 0x02
    FRAME_END = 0x03
    ESCAPE = 0x1B


class Command(IntEnum):
    Poll = ord("P")

    SetPaperIn = ord("A")
    SetPaperOut = ord("a")

    SetPlatenIn = ord("L")
    SetPlatenOut = ord("l")

    RecordingStart = ord("R")
    RecordingStop = ord("r")

    def to_bytes(self) -> bytes:
        return bytes([ByteCode.FRAME_START, self, ByteCode.FRAME_END])


class Repsonse(IntEnum):
    Acknowledge = 0x06

    MotorAdvance = ord("F")
    MotorReverse = ord("B")
    BurnLine = ord("U")


class FrameProtocol:
    class State(Enum):
        Idle = auto()
        Processing = auto()

    def __init__(self) -> None:
        self.state: FrameProtocol.State = self.State.Idle
        self.escape_next: bool = False
        self.frame_buffer: bytearray = bytearray()

    def process_byte(self, byte: int) -> bytes | None:
        if self.state == FrameProtocol.State.Idle:
            if byte == ByteCode.FRAME_START:
                self.frame_buffer.clear()
                self.state = FrameProtocol.State.Processing
            return None

        # Processing.
        if self.escape_next:
            self.frame_buffer.append(byte)
            self.escape_next = False
            return None

        if byte == ByteCode.ESCAPE:
            self.escape_next = True
            return None

        if byte == ByteCode.FRAME_START:
            self.state = FrameProtocol.State.Idle
            return None

        if byte == ByteCode.FRAME_END:
            self.state = FrameProtocol.State.Idle
            return bytes(self.frame_buffer)

        self.frame_buffer.append(byte)
        return None


class PrintoutBuilder:
    def __init__(self) -> None:
        self._image: list[NDArray[uint8]] = [np.zeros(HEAD_WIDTH).astype(uint8)]
        self._line: int = 0

    def line_advance(self) -> None:
        self._line += 1

        if self._line >= len(self._image):
            self._image.append(np.zeros(HEAD_WIDTH).astype(uint8))

    def line_reverse(self) -> None:
        if self._line == 0:
            self._image.insert(0, np.zeros(HEAD_WIDTH).astype(uint8))
        else:
            self._line -= 1

    def burn_line(self, line: NDArray[uint8]) -> None:
        self._image[self._line] = np.bitwise_or(
            self._image[self._line], line, dtype=uint8
        )

    def get_image(self) -> NDArray[uint8] | None:
        if len(self._image) <= 1:
            return None

        image = np.vstack((self._image[:-1]), dtype=uint8)
        return np.multiply(image, 255, dtype=uint8)

    def clear(self) -> None:
        self._image: list[NDArray[uint8]] = [self._image[-1]]
        self._line: int = 0


class MechAnalyser:
    def __init__(self, serial: Serial) -> None:
        self._serial: Final[Serial] = serial
        self._data: bytearray = bytearray()
        self._printout: PrintoutBuilder = PrintoutBuilder()

    def set_paper_in(self) -> None:
        self._serial.write(Command.SetPaperIn.to_bytes())

    def set_paper_out(self) -> None:
        self._serial.write(Command.SetPaperOut.to_bytes())

    def set_platen_in(self) -> None:
        self._serial.write(Command.SetPlatenIn.to_bytes())

    def set_platen_out(self) -> None:
        self._serial.write(Command.SetPlatenOut.to_bytes())

    def start_capture(self) -> None:
        self._serial.write(Command.RecordingStart.to_bytes())

    def stop_capture(self) -> None:
        self._serial.write(Command.RecordingStop.to_bytes())

    def process(self) -> None:
        new_data: bytes | None = self._serial.read_all()

        if new_data is None or len(new_data) == 0:
            return

        data: bytes = self._data + new_data
        self._data.clear()

        # Process data into frames.
        parser = FrameProtocol()
        frames: list[bytes] = []

        for byte in data:
            frame = parser.process_byte(byte)
            self._data.append(byte)

            if frame is not None:
                frames.append(frame)
                self._data.clear()

        # Process frames into printout
        for frame in frames:
            if frame.startswith(bytes([Repsonse.MotorAdvance])):
                self._printout.line_advance()

            if frame.startswith(bytes([Repsonse.MotorReverse])):
                self._printout.line_reverse()

            if frame.startswith(bytes([Repsonse.BurnLine])):
                line_data = bytearray(frame.removeprefix(bytes([Repsonse.BurnLine])))
                line_data.reverse()
                data_bytes = [uint8(byte) for byte in line_data]

                line: NDArray[uint8] = np.array(data_bytes, dtype=uint8)
                line = np.unpackbits(line, bitorder="big")
                self._printout.burn_line(line)

    def get_printout(self) -> Printout | None:
        image = self._printout.get_image()
        return Printout(image) if image is not None else None

    def take_printout(self) -> Printout | None:
        image = self._printout.get_image()
        self._printout.clear()
        return Printout(image) if image is not None else None

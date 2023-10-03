from enum import Enum, IntEnum, auto


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

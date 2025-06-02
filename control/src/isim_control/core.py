from pymmcore_plus import CMMCorePlus
from contextlib import contextmanager
from typing import Iterator


class ISIMCore(CMMCorePlus):
    def setRelativeXYPosition(self, device: str, dx: float, dy: float) -> None:
        if not (dx or dy):
            return
        x, y = self.getXPosition(device), self.getYPosition(device)
        with self._stage_moved_emission_ensured(device, x + dx, y + dy):
            super().setXYPosition(device, x + dx, y + dy)


    @contextmanager
    def _stage_moved_emission_ensured(self, *args, **kwargs) -> Iterator[None]:
        """Context that emits events if any stage device moves."""
        if args[0] is str:
            device = args[0]
        else:
            device = self.getXYStageDevice()

        class Receiver:
            moved = False

            def receive(self, *args):
                self.moved = True

        receiver = Receiver()
        self.events.XYStagePositionChanged.connect(receiver.receive)
        yield
        if not receiver.moved:
            self.waitForDevice(device)
            pos = self.getXYPosition(device)
            self.events.XYStagePositionChanged.emit(device, *pos)
        del receiver
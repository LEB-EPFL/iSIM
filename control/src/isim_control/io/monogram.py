import pygame
import time
from psygnal import Signal
from threading import Thread
from pymmcore_plus import CMMCorePlus

CUTOFF_SPEEDUP = 80 # This is 1/ms for last value change
# CUTOFF_SPEEDDOWN = 5
CUTOFF_SPEED = 200
MAX_POSITION = 202 #um

class MonogramCC():

    def __init__(self, mmcore: CMMCorePlus):
        super().__init__()
        pygame.init()
        self.init_controller()
        self._mmc = mmcore
        self.thread = Thread(target=self.start_listener, args=(self.device,))
        self.thread.start()

    def init_controller(self):
        joystick_count = pygame.joystick.get_count()
        if joystick_count == 0:
            raise OSError('No joystick found')
        else:
            self.device = pygame.joystick.Joystick(0)
            self.device.init()

    def start_listener(self, device):
        self.listener = self.Listener(device, self._mmc)
        self.listener.new_pos_event.connect(self._mmc.setPosition)
        self.listener.start()

    def stop(self):
        self.listener.stop()


    class Listener():
        new_pos_event = Signal(float)
        def __init__(self, device, mmcore: CMMCorePlus):
            super().__init__()
            self._device = device
            self._mmc = mmcore

            # Initialize to the current position of the stage
            self.z_pos = self._mmc.getPosition(self._mmc.getFocusDevice())/MAX_POSITION
            # self.offset = self.last_value = self.z_pos
            # self.z_pos = self._device.get_axis(0)
            self.last_value = self._device.get_axis(0)
            self.last_value_turn = None
            self.offset = self.last_value
            self.last_time = time.perf_counter()
            self.turn = 0
            self.total_relative_move = 0
            self.last_send = time.perf_counter()

            self.stop_requested = False

        def start(self):
            while not self.stop_requested:
                event = pygame.event.wait(timeout=500)
                if event.type == 1536:  # AxisMotion
                    if event.axis == 0:
                        self.updatePos(event.value)
                if event.type == 1540:  # ButtonUp
                    print(event.button)
                    if event.button == 0:
                        pygame.quit()
                        break
                    if event.button == 1:
                        self.resetPos()
                    if event.button == 2:
                        self.monogram_stop_live_event.emit()

        def resetPos(self):
            self.z_pos = 0
            self.offset = self._device.get_axis(0)
            self.turn = 0

        def updatePos(self, new_value):
            if self.last_value > 0.5 and new_value < -0.5:
                self.turn = self.turn + 2
            elif self.last_value < -0.5 and new_value > 0.5:
                self.turn = self.turn - 2
            self.last_value = new_value
            if not self.last_value_turn:
                self.last_value_turn = self.last_value

            new_value_turn = new_value + self.turn
            relative_move = (new_value_turn - self.last_value_turn)/20
            self.last_value_turn = new_value_turn

            self.z_pos = self.z_pos + relative_move
            self.z_pos = min([self.z_pos, 1])
            self.z_pos = max([self.z_pos, 0])
            self.scaled_z = self.z_pos * MAX_POSITION

            now = time.perf_counter()
            if now - self.last_send > 0.05:
                self.new_pos_event.emit(self.scaled_z)
                self.last_send = now

        def stop(self):
            self.stop_requested = True

if __name__ == "__main__":
    from pymmcore_widgets import StageWidget
    from qtpy.QtWidgets import QApplication
    app = QApplication([])
    mmc = CMMCorePlus()
    try:
        mmc.loadSystemConfiguration("C:/iSIM/iSIM/mm-configs/pymmcore_plus.cfg")
        stage = StageWidget("MCL NanoDrive Z Stage", mmcore=mmc)
        mmc.setProperty("MCL NanoDrive Z Stage", "Settling time (ms)", 20)
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        print("Could not load iSIM devices, going Democonfig")
        mmc.loadSystemConfiguration()
        stage = StageWidget("Z", mmcore=mmc)
    monogram = MonogramCC(mmcore=mmc)
    stage.show()
    app.exec_()
    monogram.stop()
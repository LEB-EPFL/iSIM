import pygame
import time
from psygnal import Signal
from threading import Thread
from pymmcore_plus import CMMCorePlus
from isim_control.pubsub import Publisher, Subscriber

CUTOFF_SPEEDUP = 80 # This is 1/ms for last value change
# CUTOFF_SPEEDDOWN = 5
CUTOFF_SPEED = 200
MAX_POSITION = 202 #um

class MonogramCC():

    def __init__(self, mmcore: CMMCorePlus, publisher: Publisher = None):
        super().__init__()
        pygame.init()
        self.init_controller()
        self._mmc = mmcore
        self.pub = publisher
        self.thread = Thread(target=self.start_listener, args=(self.device,))
        self.thread.start()

        self.sub = Subscriber(["gui"], {"live_button_clicked": [self.live_button_clicked],})
        self.live_mode = False

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
        self.listener.stop_live_event.connect(self._stop_live)
        self.listener.laser_intensity_event.connect(self._laser_intensity)
        self.listener.activate_channel_event.connect(self._channel_activate)
        self.listener.start()

    def live_button_clicked(self, value):
        self.live_mode = value

    def _stop_live(self):
        self.pub.publish("gui", "live_button_clicked", [not self.live_mode])

    def _laser_intensity(self, laser, value):
        self.pub.publish("gui", "laser_intensity_changed", [laser, value])

    def _channel_activate(self, channel):
        self.pub.publish("gui", "channel_activated", [channel])

    def stop(self):
        self.listener.stop()


    class Listener():
        new_pos_event = Signal(float)
        stop_live_event = Signal()
        laser_intensity_event = Signal(int, float)
        activate_channel_event = Signal(str)
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
            self.laser_int = [self._device.get_axis(i) for i in range(1,4)]

            self.stop_requested = False

        def start(self):
            while not self.stop_requested:
                event = pygame.event.wait(timeout=500)
                if event.type == 1536:  # AxisMotion
                    if event.axis == 0: #Big wheel
                        self.updatePos(event.value)
                    if event.axis in [1, 2, 3]: #Laser
                        increment = event.value - self.laser_int[event.axis-1]
                        if increment > 5 or increment < -5:
                            break
                        value = 1 if increment > 0 else -1
                        self.laser_intensity_event.emit(event.axis, value)
                        self.laser_int[event.axis-1] = event.value
                if event.type == 1540:  # ButtonUp
                    match event.button:
                        case 0:
                            pygame.quit()
                            break
                        case 1:
                            self.resetPos()
                        case 2:
                            self.stop_live_event.emit()
                        case 3:
                            self.activate_channel_event.emit("488")
                        case 4:
                            self.activate_channel_event.emit("561")
                        case 5:
                            self.activate_channel_event.emit("led")


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
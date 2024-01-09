import numpy as np
import nidaqmx
import nidaqmx
from pymmcore_plus import CMMCorePlus
from threading import Timer
import time
from isim_control.ni.devices import NIDeviceGroup
from useq import MDAEvent
from threading import Thread, Lock, Event
import logging

CONTINUOUS = nidaqmx.constants.AcquisitionType.CONTINUOUS

class LiveEngine():
    def __init__(self,
                 task: nidaqmx.Task = None,
                 device_group: NIDeviceGroup = None,
                 mmcore: CMMCorePlus = None,
                 settings: dict = None):
        self._mmc = mmcore or CMMCorePlus.instance()
        self.settings = settings or iSIMSettings()
        self.fps = 5
        self.timer = None
        self.devices = device_group

        if task is None:
            self.task = nidaqmx.Task()
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao0') # galvo channel
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao1') # z stage
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao2') # camera
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao3') # aotf blanking channel
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao4') # aotf 488 channel
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao5') # aotf 561 channel
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao6') # LED channel
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao7') # twitcher channel
            self.task.timing.cfg_samp_clk_timing(rate=self.settings['ni']['sample_rate'],
                                                 samps_per_chan=settings['ni']['total_points'] +
                                                 settings['ni']['readout_points']//3*2)
        else:
            self.task = task


    def _on_sequence_started(self):
        "STARTING LIVE"
        self.timer = LiveTimer(1/self.fps, self.settings, self.task, self.devices, self._mmc)
        self.timer.start()
        logging.debug("Live started from LiveEngine")

    def _on_sequence_stopped(self):
        if self.timer:
            self.timer.request_cancel()
            if self.timer.running:
                logging.debug("Live still running, trying again in 0.15s")
                Timer(0.15, self._on_sequence_stopped).start()
                return
        self.timer = None

    def restart(self):
        if self.timer:
            #print("Restart live")
            if self.timer.running:
                #print("LiveTimer still running")
                self.timer.request_cancel()
                Timer(0.15, self.restart).start()
                return
            self.timer = None
            #print("Now restarting")
            self.timer = LiveTimer(0, self.settings, self.task, self.devices, self._mmc)
            self.timer.start()

    def snap(self):
        if self.timer:
            return
        self.timer = LiveTimer(1/self.fps, self.settings, self.task, self.devices, self._mmc,
                                snap_mode=True)
        self.timer.stop_event.set()
        self.timer.start()
        self.timer = None

    def update_settings(self, settings):
        self.settings = settings['live']
        if self.timer:
            if self.settings['fps'] != self.fps:
                self.timer.interval = 1/self.settings['fps']
        self.fps = self.settings['fps']


class LiveTimer(Timer):
    def __init__(self, interval:float, settings: dict, task: nidaqmx.Task, devices: NIDeviceGroup,
                 mmcore: CMMCorePlus, snap_mode=False):
        super().__init__(interval, None)
        self.settings = settings
        self.task = task
        self.devices = devices
        self._mmc = mmcore
        self.snap_mode = snap_mode
        self.running = False
        self.snapping = False

        self.snap_lock = Lock()
        self.stop_event = Event()
        self.snapping = Event()

    def run(self):
        self.running = True
        thread = None
        while not self.finished.wait(self.interval):
            if self.stop_event.is_set() and not self.snap_mode:
                break
            thread = Thread(target=self.snap_and_get)
            self.snap_lock.acquire()
            thread.start()
            self.task.write(self.one_frame())
            logging.debug("NI task written")
            self.snap_lock.acquire()
            self.task.start()
            logging.debug("NI task started, trigger sent to camera")
            self.task.wait_until_done()
            self.task.stop()
            if self.stop_event.is_set():
                break
        #print("Waiting for THREAD")
        if thread:
            thread.join(0.2)
        # We resend the data in case the camera has not finished and needs an additional trigger
        while self.snapping.is_set():
            self.task.write(self.one_frame(clean_up=True))
            self.task.start()
            self.task.wait_until_done()
            self.task.stop()
        self.running = False

    def snap_and_get(self):
        self.snap_lock.release()
        try:
            self.snapping.set()
            self._mmc.snapImage()
            self.snapping.clear()
            self._mmc.events.liveFrameReady.emit(self._mmc.getImage(fix=False),
                                                 MDAEvent(channel=self.settings['channel']),
                                                 self._mmc.getTags())
        except Exception as e:
            self.request_cancel()
        self.snap_lock.release()

    def request_cancel(self):
        self.stop_event.set()

    def one_frame(self, clean_up=False):
        event = MDAEvent(channel={'config':self.settings['channel']})
        next_event = event
        ni_data = self.devices.get_data(event, next_event, live=True)
        if not clean_up:
            return ni_data
        ni_data[-2, :] = np.zeros(ni_data.shape[1])
        ni_data[3, :] = np.zeros(ni_data.shape[1])
        return ni_data


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication, QGridLayout, QWidget
    from pymmcore_widgets import LiveButton, ImagePreview, StageWidget
    from isim_control.settings import iSIMSettings
    app = QApplication([])

    mmc = CMMCorePlus().instance()
    mmc.loadSystemConfiguration("C:/iSIM/Micro-Manager-2.0.2/221130.cfg")
    mmc.setCameraDevice("PrimeB_Camera")
    mmc.setProperty("PrimeB_Camera", "TriggerMode", "Edge Trigger")
    mmc.setProperty("Sapphire", "State", 1)
    mmc.setProperty("Quantum_561nm", "Laser Operation", "On")
    mmc.setAutoShutter(False)
    mmc.setExposure(129)


    settings = iSIMSettings()
    settings['live']['channel'] = "488"
    devices = NIDeviceGroup(settings['ni'])

    class MiniLiveWidget(QWidget):
        def __init__(self):
            super().__init__()
            stage1 = StageWidget("MicroDrive XY Stage")
            stage2 = StageWidget("MCL NanoDrive Z Stage")
            live_btn = LiveButton()
            image_prev = ImagePreview()
            self.setLayout(QGridLayout())
            self.layout().addWidget(image_prev, 0, 0, 1, 2)
            self.layout().addWidget(live_btn, 1, 0)
            self.layout().addWidget(stage1, 2, 0)
            self.layout().addWidget(stage2, 2, 1)

    gui = MiniLiveWidget()
    gui.show()
    engine = LiveEngine(mmcore=mmc, settings=settings, device_group=devices)

    app.exec_()
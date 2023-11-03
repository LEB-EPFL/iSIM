import numpy as np
import nidaqmx
import nidaqmx
from pymmcore_plus import CMMCorePlus
from threading import Timer
import time
from isim_control.ni.devices import NIDeviceGroup
from useq import MDAEvent

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
                                                 sample_mode=CONTINUOUS)
        else:
            self.task = task

        self._mmc.events.continuousSequenceAcquisitionStarted.connect(
            self._on_sequence_started
        )
        self._mmc.events.sequenceAcquisitionStopped.connect(self._on_sequence_stopped)

    def _on_sequence_started(self):
        self.task.start()
        self.timer = LiveTimer(1/self.fps, self.settings, self.task, self.devices)
        self.timer.start()

    def _on_sequence_stopped(self):
        try:
            self.timer.cancel()
            self.timer = None
        except:
            print("Acquisition not yet started")
        self.task.write(np.zeros(self.task.number_of_channels))
        time.sleep(0.5)
        self.task.stop()

    def update_settings(self, settings):
        self.settings = settings['live']
        if self.timer:
            if self.settings['fps'] != self.fps:
                self.timer.interval = 1/self.settings['fps']
        self.fps = self.settings['fps']


class LiveTimer(Timer):
    def __init__(self, interval:float, settings: dict, task: nidaqmx.Task, devices: NIDeviceGroup):
        super().__init__(interval, None)
        self.settings = settings
        self.task = task
        self.devices = devices

    def run(self):
        while not self.finished.wait(self.interval):
            self.task.write(self.one_frame())

    def one_frame(self):
        event = MDAEvent(channel={'config':self.settings['channel']})
        next_event = event
        return self.devices.get_data(event, next_event, live=True)



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
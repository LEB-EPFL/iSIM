import numpy as np
from nidaqmx import Task as NITask
import nidaqmx
from pymmcore_plus import CMMCorePlus
from threading import Timer
import time

CONTINUOUS = nidaqmx.constants.AcquisitionType.CONTINUOUS

class LiveEngine():
    def __init__(self, task: NITask = None, mmcore: CMMCorePlus = None, settings: dict = None):
        self._mmc = mmcore or CMMCorePlus.instance()
        self.settings = settings or {}
        self.fps = 5
        self.timer = None

        if task is None:
            self.task = NITask()
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao2')
            self.task.ao_channels.add_ao_voltage_chan('Dev1/ao6')
            self.task.timing.cfg_samp_clk_timing(rate=9600, sample_mode=CONTINUOUS)
        else:
            self.task = task

        self._mmc.events.continuousSequenceAcquisitionStarted.connect(
            self._on_sequence_started
        )
        self._mmc.events.sequenceAcquisitionStopped.connect(self._on_sequence_stopped)

    def _on_sequence_started(self):
        self.task.start()
        self.timer = LiveTimer(1/self.fps, self.settings, self.task)
        self.timer.start()

    def _on_sequence_stopped(self):
        try:
            self.timer.cancel()
            self.timer = None
        except:
            print("Acquisition not yet started")
        self.task.write(np.array([[0], [0]]))
        time.sleep(0.5)
        self.task.stop()

    def update_settings(self, settings):
        self.settings = settings
        if self.timer:
            if settings['fps'] != self.fps:
                self.timer.interval = 1/settings['fps']
        self.fps = settings['fps']


class LiveTimer(Timer):
    def __init__(self, interval:float, settings: dict, task: NITask,):
        super().__init__(interval, None)
        self.settings = settings
        self.task = task

    def run(self):
        while not self.finished.wait(self.interval):
            self.task.write(self.one_frame())

    def one_frame(self):
        #TODO built a real frame from the "live" settings
        # This will need the devices for that.
        camera = np.hstack([np.ones(100)*5, np.zeros(10)])
        led = camera/5*self.settings['ni']['laser_powers']['led']/20
        return np.vstack([camera, led])



if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication
    from pymmcore_widgets import LiveButton, ImagePreview
    app = QApplication([])

    mmc = CMMCorePlus().instance()
    mmc.loadSystemConfiguration("C:/iSIM/Micro-Manager-2.0.2/prime_only.cfg")
    mmc.setCameraDevice("Prime")
    mmc.setProperty("Prime", "TriggerMode", "Edge Trigger")

    live_btn = LiveButton()
    image_prev = ImagePreview()
    image_prev.show()
    live_btn.show()

    engine = LiveEngine(mmcore=mmc)

    app.exec_()
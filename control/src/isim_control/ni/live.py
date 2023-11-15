import numpy as np
import nidaqmx
import nidaqmx
from pymmcore_plus import CMMCorePlus
from threading import Timer
import time
from isim_control.ni.devices import NIDeviceGroup
from useq import MDAEvent
from threading import Thread, Lock, Event

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

    def _on_sequence_stopped(self):
        try:
            self.timer.request_cancel()
            self.timer = None
        except:
            #print("Acquisition not yet started")

    def restart(self):
        if self.timer:
            #print("Restart live")
            if self.timer.running:
                #print("LiveTimer still running")
                self.timer.request_cancel()
                Timer(0.3, self.restart).start()
                return
            self.timer = None
            #print("Now restarting")
            self.timer = LiveTimer(1/self.fps, self.settings, self.task, self.devices, self._mmc)
            self.timer.start()

    def update_settings(self, settings):
        self.settings = settings['live']
        if self.timer:
            if self.settings['fps'] != self.fps:
                self.timer.interval = 1/self.settings['fps']
        self.fps = self.settings['fps']


class LiveTimer(Timer):
    def __init__(self, interval:float, settings: dict, task: nidaqmx.Task, devices: NIDeviceGroup,
                 mmcore: CMMCorePlus):
        super().__init__(interval, None)
        self.settings = settings
        self.task = task
        self.devices = devices
        self._mmc = mmcore
        self.running = False
        self.snapping = False

        self.snap_lock = Lock()
        self.stop_event = Event()
        self.snapping = Event()

    def run(self):
        self.running = True
        while not self.finished.wait(self.interval):
            if self.stop_event.is_set():
                break
            self.snap_lock.acquire()
            #print("live_running")
            thread = Thread(target=self.snap_and_get)
            thread.start()
            self.task.write(self.one_frame())
            self.snap_lock.acquire()
            #print(time.perf_counter(), "Send trigger")
            self.task.start()
            self.task.wait_until_done()
            self.task.stop()
            if self.stop_event.is_set():
                break

        #print("Waiting for THREAD")
        thread.join(1)
        #we resend the data in case the camera has not finished
        while self.snapping.is_set():
            #print("Rewriting clean up data")
            self.task.write(self.one_frame(clean_up=True))
            self.task.start()
            self.task.wait_until_done()
            self.task.stop()
        #print("Live TIMER DONE")
        self.running = False

    def snap_and_get(self):
        self.snap_lock.release()
        #print(time.perf_counter(), "SNAP")
        try:
            self.snapping.set()
            self._mmc.snapImage()
            self.snapping.clear()
            self._mmc.mda.events.frameReady.emit(self._mmc.getImage(fix=False), None,
                                                 self._mmc.getTags())
        except Exception as e:
            #print(e)
            self.request_cancel()
        #print(time.perf_counter(), "SNAPPED")
        self.snap_lock.release()

    def request_cancel(self):
        self.stop_event.set()

    def one_frame(self, clean_up=False):
        event = MDAEvent(channel={'config':self.settings['channel']})
        next_event = event
        ni_data = self.devices.get_data(event, next_event, live=True)
        if not clean_up:
            return ni_data
        else:
            #print(ni_data.shape)
            ni_data[-2, :] = np.zeros(ni_data.shape[1])
            ni_data[3, :] = np.zeros(ni_data.shape[1])
            return ni_data
        # ni_data_no_z = np.delete(ni_data, [1], axis=0)
        # #print(ni_data_no_z.shape)
        # return np.delete(ni_data, [1], axis=0)



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
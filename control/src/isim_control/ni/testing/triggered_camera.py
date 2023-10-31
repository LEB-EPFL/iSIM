from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import MDAEngine
from useq import MDAEvent, MDASequence
import nidaqmx
import numpy as np
import time
from threading import Thread, Lock
from datetime import datetime



try:
    from pymmcore_widgets import ImagePreview
    from qtpy.QtWidgets import QApplication
    pyqt_installed = True
except:
    pyqt_installed = False

EXPOSURE = 100

mmc = CMMCorePlus()
mmc.loadSystemConfiguration("C:/iSIM/Micro-Manager-2.0.2/prime_only.cfg")

def makePulse(start, end, offset, n_points):
    DutyCycle=10/n_points
    up = np.ones(round(DutyCycle*n_points))*start
    down = np.ones(n_points-round(DutyCycle*n_points))*end
    pulse = np.concatenate((up,down)) + offset
    return pulse

class iSIMEngine(MDAEngine):
    def __init__(self, mmc):
        super().__init__(mmc)

        self.pre_trigger_delay = 10 #ms

        self.mmc = mmc


        self.task = nidaqmx.Task()
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao2')
        self.task2 = nidaqmx.Task()
        self.task2.ao_channels.add_ao_voltage_chan('Dev1/ao6')
        self.task.timing.cfg_samp_clk_timing(rate=48000, sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
        self.task.start()
        self.task2.start()
        self.frame_times = np.zeros(20)
        self.mmc.mda.events.frameReady.connect(self.on_frame)
        self.mmc.mda.events.sequenceFinished.connect(self.on_sequence_end)

        self.snap_lock = Lock()

        self.camera_data = makePulse(5, 0, 0, 100 )

    def setup_event(self, event):
        self.snap_lock.acquire()
        thread = Thread(target=self.snap_and_get, args=(event,))
        thread.start()
        self.task2.write(5)

    def exec_event(self, event):
        self.snap_lock.acquire()
        time.sleep(self.pre_trigger_delay/1000)
        self.task.write(self.camera_data)
        self.task2.write(0)
        return ()

    def snap_and_get(self, event):
        self.snap_lock.release()
        self._mmc.snapImage()
        self._mmc.mda.events.frameReady.emit(self._mmc.getImage(fix=False), event, self._mmc.getTags())
        self.snap_lock.release()

    def on_frame(self, image, event, meta):
        # time_here = datetime.strptime(meta["Time"], '%Y-%m-%d %H:%M:%S.%f')
        # self.frame_times[event.index['t']] = time_here.timestamp()*1000
        self.frame_times[event.index['t']] = time.perf_counter()*1000

    def on_sequence_end(self):
        frame_times = self.frame_times[self.frame_times != 0]
        mean_offset = np.mean(np.diff(frame_times))
        std = np.std(np.diff(frame_times))
        print(round(mean_offset*100)/100, "±", round(std*100)/100, "ms, max",
              max(np.diff(frame_times)), "#", len(frame_times))
        pre_trigger_delay = float(self.mmc.getProperty("Prime", "Timing-ReadoutTimeNs"))/1e6
        pre_trigger_delay = pre_trigger_delay if pre_trigger_delay > 0 else None
        if pre_trigger_delay is None:
            mode = self.mmc.getProperty("Prime", "ReadoutRate")
            pre_trigger_delay = 12.94 if "100MHz" in mode else 5.85
        print("Excpected fastest cycle time: ",
              EXPOSURE + float(self.mmc.getProperty("Prime", "Timing-ReadoutTimeNs"))/1e6 +
              self.pre_trigger_delay + pre_trigger_delay)
        print()
        print(float(self.mmc.getProperty("Prime", "Timing-PreTriggerDelayNs")))


mmc.setExposure(EXPOSURE)
mmc.setCameraDevice("Prime")
mmc.setProperty("Prime", "TriggerMode", "Edge Trigger")
time.sleep(1)

mmc.mda.set_engine(iSIMEngine(mmc))

sequence = MDASequence(
    time_plan={"interval": 0.1, "loops": 20},
    channels=[{"config": "488"}]
)
mmc.run_mda(sequence)




# if __name__ == "__main__" and pyqt_installed:
#     app = QApplication([])
#     image_frame = ImagePreview()
#     image_frame.show()
#     mmc.mda.events.frameReady.connect(image_frame._on_image_snapped)
#     mmc.run_mda(sequence)
#     app.exec_()
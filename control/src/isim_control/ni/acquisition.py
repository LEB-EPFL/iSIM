from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import MDAEngine
import nidaqmx
import nidaqmx.stream_writers
from threading import Thread, Lock, Event
import numpy as np
import time
import copy

from useq import MDAEvent
from isim_control.ni.devices import NIDeviceGroup
from isim_control.settings import iSIMSettings

CONTINUOUS = nidaqmx.constants.AcquisitionType.CONTINUOUS

class AcquisitionEngine(MDAEngine):
    def __init__(self, mmc: CMMCorePlus, device_group: NIDeviceGroup = None,
                 settings: dict|None = None):
        super().__init__(mmc)

        self.mmc = mmc
        self.settings = settings or iSIMSettings()
        self.device_group = device_group

        self.task = self.device_group.task
        self.stream = self.device_group.stream
        self.mmc.mda.events.sequenceFinished.connect(self.on_sequence_end)
        self.snap_lock = Lock()

        self.running = Event()

    def setup_event(self, event: MDAEvent):
        try:
            next_event = next(self.internal_event_iterator)
        except StopIteration:
            next_event = None
        self.ni_data = self.device_group.get_data(event, next_event)
        thread = Thread(target=self.snap_and_get, args=(event,))

        self.snap_lock.acquire()
        thread.start()
        try:
            self.task.stop()
        except:
            pass
        self.stream.write_many_sample(self.ni_data)

        #TODO this does not work yet but might be needed for grids
        # super().setup_event(event)

    def exec_event(self, event: MDAEvent):
        # Check that the camera has been asked to snap and start the generation on the DAQ
        self.snap_lock.acquire()
        self.task.start()
        return ()

    def snap_and_get(self, event):
        self.snap_lock.release()
        self._mmc.snapImage()
        self.snap_lock.release()
        self._mmc.mda.events.frameReady.emit(self._mmc.getImage(fix=False), event,
                                             self._mmc.getTags())

    def on_sequence_end(self, sequence):
        self.snap_lock.acquire()
        self.task.wait_until_done()
        self.task.stop()
        self.snap_lock.release()
        self.running.clear()

    def setup_sequence(self, sequence):
        # Potentially we could set up data for the whole sequence here
        self.sequence = copy.deepcopy(sequence)
        self.internal_event_iterator = self.sequence.iter_events()
        next(self.internal_event_iterator)
        self._mmc.setPosition(self.settings['ni']['relative_z'])
        self.running.set()

    def update_settings(self, settings):
        self.settings = settings



class TimedAcquisitionEngine(AcquisitionEngine):
    def __init__(self, mmc: CMMCorePlus, device_group: NIDeviceGroup = None,
                 settings: dict|None = None):
        super().__init__(mmc, device_group, settings)

    def on_sequence_end(self, sequence):
        self.show_timing()
        return super().on_sequence_end(sequence)

    def setup_sequence(self, sequence):
        self.frame_times = np.zeros(sequence.sizes['t'])
        return super().setup_sequence(sequence)

    def on_frame(self, image, event, meta):
        # time_here = datetime.strptime(meta["Time"], '%Y-%m-%d %H:%M:%S.%f')
        # self.frame_times[event.index['t']] = time_here.timestamp()*1000
        self.frame_times[event.index['t']] = time.perf_counter()*1000

    def show_timing(self):
        frame_times = self.frame_times[self.frame_times != 0]
        mean_offset = np.mean(np.diff(frame_times))
        std = np.std(np.diff(frame_times))
        print(round(mean_offset*100)/100, "±", round(std*100)/100, "ms, max",
              max(np.diff(frame_times)), "#", len(frame_times))
        # pre_trigger_delay = float(self.mmc.getProperty("PrimeB_Camera", "Timing-ReadoutTimeNs"))/1e6
        # pre_trigger_delay = pre_trigger_delay if pre_trigger_delay > 0 else None
        # if pre_trigger_delay is None:
        #     mode = self.mmc.getProperty("PrimeB_Camera", "ReadoutRate")
        #     pre_trigger_delay = 12.94 if "100MHz" in mode else 5.85
        print("Excpected fastest cycle time: ",
              self.settings['exposure_time']*1000 + 2*float(self.mmc.getProperty("PrimeB_Camera", "Timing-ReadoutTimeNs"))/1e6 +
              + 8 + 3)
        print()



if __name__ == "__main__":
    import useq
    from pymmcore_widgets import ImagePreview
    EXPOSURE = 100
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration("C:/iSIM/Micro-Manager-2.0.2/prime_only.cfg")
    mmc.setExposure(EXPOSURE)
    mmc.setCameraDevice("Prime")
    mmc.setProperty("Prime", "TriggerMode", "Edge Trigger")
    mmc.setProperty("Prime", "ReadoutRate", "100MHz 16bit")
    mmc.setProperty("Sapphire", "State", 1)
    mmc.setProperty("Laser", "Laser Operation", "On")
    mmc.setAutoShutter(False)
    time.sleep(1)

    from qtpy.QtWidgets import QApplication
    app = QApplication([])
    preview = ImagePreview(mmcore=mmc)
    mmc.mda.events.frameReady.connect(preview._on_image_snapped)
    preview.show()


    mmc.mda.set_engine(AcquisitionEngine(mmc))

    sequence = useq.MDASequence(
        time_plan={"interval": 4, "loops": 10},
        channels=[{"config": "488"}, {"config": "561"}],
        z_plan={"range": 3, "step": 1},
        axis_order="tpgzc"
    )
    mmc.run_mda(sequence)
    app.exec_()
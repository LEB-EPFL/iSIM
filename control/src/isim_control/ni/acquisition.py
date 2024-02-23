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
WAIT_TIME = 2 #Seconds to wait before starting acq
class AcquisitionEngine(MDAEngine):
    def __init__(self, mmc: CMMCorePlus, device_group: NIDeviceGroup = None,
                 settings: dict|None = None):
        super().__init__(mmc)

        self.mmc = mmc
        self.settings = settings or iSIMSettings()
        self.device_group = device_group
        self.previous_exposure = None

        self.task = self.device_group.task
        self.stream = self.device_group.stream
        self.mmc.mda.events.sequenceFinished.connect(self.on_sequence_end)
        self.snap_lock = Lock()

        self.running = Event()

    def setup_event(self, event: MDAEvent):
        #TODO: If we want a z_offset for the LED channel, this might break it. We would then have
        # handle that in the NI device.
        t0 = time.perf_counter()
        sub_event = self._adjust_event_properties(event)
        if self.use_filter_wheel:
            set_filter = {"LED": "#NoFilter", "488": "488", "561": "561"}[sub_event.channel.config]
            self.mmc.setProperty("FilterWheel", "Label", set_filter)
            self.mmc.waitForDevice("FilterWheel")

        super().setup_event(sub_event)

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
        # Delay the first frame a little so that things have time to set up
        if sum(sub_event.index.values()) == 0:
            #Offset the time we needed to set up the acqusition in the runner
            self.mmc._mda_runner._paused_time +=time.perf_counter() - t0
            time.sleep(WAIT_TIME)
            self.mmc._mda_runner._paused_time += WAIT_TIME


    def exec_event(self, event: MDAEvent):
        # Check that the camera has been asked to snap and start the generation on the DAQ
        self.snap_lock.acquire()
        self.task.start()
        return ()

    def snap_and_get(self, event):
        self.snap_lock.release()
        self._mmc.snapImage()
        self.snap_lock.release()
        meta = self._mmc.getTags()
        meta["ElapsedTime-ms"] = (meta["PerfCounter"] - self._t0) * 1000
        self._mmc.mda.events.frameReady.emit(self._mmc.getImage(fix=False), event, meta)

    def on_sequence_end(self, sequence):
        self.snap_lock.acquire()
        self.task.wait_until_done()
        self.task.stop()
        self.snap_lock.release()
        self.running.clear()
        if self.previous_exposure != self._mmc.getExposure():
            self._mmc.setExposure(self.previous_exposure)
            print("EXPOSURE RESET FOR LIVE", self.previous_exposure)

    def setup_sequence(self, sequence):
        self.sequence = copy.deepcopy(sequence)
        # This we will use to know about the next event (setting z_position for example)
        self.internal_event_iterator = self.sequence.iter_events()
        next(self.internal_event_iterator)
        self._mmc.setPosition(min(self.settings['ni']['relative_z'], 202))
        self.use_filter_wheel = self.settings['use_filters']
        if self.use_filter_wheel:
            self.start_filter = self.mmc.getProperty("FilterWheel", "Label")
        self.start_xy_position = self._mmc.getXYPosition()
        self._t0 = time.perf_counter()
        self.running.set()

    def teardown_sequence(self, sequence):
        # Reset the position, important for grid plan
        self._mmc.setXYPosition(*self.start_xy_position)
        if self.use_filter_wheel:
            self.mmc.setProperty("FilterWheel", "Label", self.start_filter)

    def update_settings(self, settings):
        self.settings = settings

    def adjust_camera_exposure(self, exposure):
        self.previous_exposure = self._mmc.getExposure()
        print("EXPOSURE SET FOR ACQ", self.previous_exposure)
        if self.previous_exposure != exposure:
            self._mmc.setExposure(exposure)
            self._mmc.waitForDevice(self.mmc.getCameraDevice())

    def _adjust_event_properties(self, event):
        """We want the exposure set in the Channel to be the 'real' exposure,
           so we set the exposure of the event to None, so that it's not set in the MDAEngine setup
           The same the z position..."""
        event_dict = event.model_dump()
        event_dict['exposure'] = None
        event_dict['z_pos'] = None
        if self.start_xy_position and not event_dict['x_pos'] is None:
            event_dict['x_pos'] = event_dict['x_pos'] + self.start_xy_position[0]
            event_dict['y_pos'] = event_dict['y_pos'] + self.start_xy_position[1]
        return MDAEvent(**event_dict)

class TimedAcquisitionEngine(AcquisitionEngine):
    def __init__(self, mmc: CMMCorePlus, device_group: NIDeviceGroup = None,
                 settings: dict|None = None):
        super().__init__(mmc, device_group, settings)
        self.mmc.mda.events.frameReady.connect(self.on_frame)

    def on_sequence_end(self, sequence):
        self.show_timing()
        return super().on_sequence_end(sequence)

    def setup_sequence(self, sequence):
        self.frame_times = np.zeros(sequence.sizes['t'])
        return super().setup_sequence(sequence)

    def on_frame(self, image, event, meta):
        self.frame_times[event.index['t']] = time.perf_counter()*1000

    def show_timing(self):
        frame_times = self.frame_times[self.frame_times != 0]
        mean_offset = np.nanmean(np.diff(frame_times))
        std = np.nanstd(np.diff(frame_times))
        print(round(mean_offset*100)/100, "±", round(std*100)/100, "ms, max",
              max(np.diff(frame_times)), "#", len(frame_times))
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
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import MDAEngine
import nidaqmx
from threading import Thread, Lock
import numpy as np
import time
import copy

from useq import MDAEvent
from isim_control.ni.devices import NIDeviceGroup
from isim_control.settings import iSIMSettings

class AcquisitionEngine(MDAEngine):
    def __init__(self, mmc: CMMCorePlus, device_group: NIDeviceGroup = None,
                 settings: dict|None = None):
        super().__init__(mmc)

        self.pre_trigger_delay = 10 #ms
        self.mmc = mmc
        self.settings = settings or iSIMSettings()
        self.device_group = device_group

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
                                             sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
        self.mmc.mda.events.sequenceFinished.connect(self.on_sequence_end)

        self.snap_lock = Lock()

    def setup_event(self, event: MDAEvent):
        try:
            next_event = next(self.internal_event_iterator) or None
        except StopIteration:
            next_event = None
        self.ni_data = self.device_group.get_data(event, next_event)
        thread = Thread(target=self.snap_and_get, args=(event,))
        self.snap_lock.acquire()
        thread.start()

    def exec_event(self, event: MDAEvent):
        self.snap_lock.acquire()
        time.sleep(self.pre_trigger_delay/1000)
        # print("ni_data shape", self.ni_data.shape)
        try:
            self.task.write(self.ni_data)
        except Exception as e:
            print(e)
            print("FAILED TO WRITE NI DATA")
        return ()

    def snap_and_get(self, event):
        self.snap_lock.release()
        self._mmc.snapImage()
        self._mmc.mda.events.frameReady.emit(self._mmc.getImage(fix=False), event,
                                             self._mmc.getTags())
        self.snap_lock.release()

    def on_sequence_end(self, sequence):
        self.snap_lock.acquire()
        self.task.write(np.zeros(self.task.number_of_channels))
        self.task.stop()
        self.snap_lock.release()

    def setup_sequence(self, sequence):
        # Potentially we could set up data for the whole sequence here
        self.sequence = copy.deepcopy(sequence)
        self.internal_event_iterator = self.sequence.iter_events()
        next(self.internal_event_iterator)
        self.task.start()
        self.task.write(np.zeros(self.task.number_of_channels))
        self._mmc.setPosition(self.settings['ni']['relative_z'])

    def update_settings(self, settings):
        self.settings = settings
        self.task.timing.cfg_samp_clk_timing(rate=settings['ni']['sample_rate'],
                                                sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
        print(settings)

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
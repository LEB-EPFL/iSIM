import os
import copy

from pymmcore_widgets import StageWidget, GroupPresetTableWidget
from qtpy.QtWidgets import QApplication, QWidget
from qtpy.QtCore import Signal, Qt

from isim_control.core import ISIMCore


from useq import MDASequence
from pymmcore_eda.actuator import MDAActuator, ButtonActuator
from pymmcore_eda.queue_manager import QueueManager
from isim_control.settings_translate import load_settings

os.environ["PYMM_STRICT_INIT_CHECKS"] = 'true'
os.environ["PYMM_PARALLEL_INIT"] = 'true'

def main():
    app = QApplication([])
    mmc = ISIMCore.instance()
    settings = load_settings()
    settings['twitchers'] = False
    settings['exposure_time'] = 0.05
    settings.calculate_ni_settings(settings['exposure_time']*1000)

    events_class = mmc.events.__class__
    new_cls = type(
        events_class.__name__, events_class.__bases__,
        {**events_class.__dict__, 'liveFrameReady': Signal(object, object, dict)},
    )
    mmc.events.__class__ = new_cls

    # Load and init the iSIM
    mmc.loadSystemConfiguration("C:/iSIM/iSIM/mm-configs/pymmcore_plus.cfg")
    print("System loaded")
    mmc.setCameraDevice("PrimeB_Camera")
    mmc.setProperty("PrimeB_Camera", "TriggerMode", "Edge Trigger")
    mmc.setProperty("PrimeB_Camera", "ReadoutRate", "100MHz 16bit")

    mmc.setProperty("Sapphire", "State", 1)
    mmc.setProperty("Quantum_561nm", "Laser Operation", "On")
    mmc.setProperty("MCL NanoDrive Z Stage", "Settling time (ms)", 30)
    mmc.setXYStageDevice("MicroDrive XY Stage")
    mmc.setExposure(settings['exposure_time']*1000)
    mmc.setAutoShutter(False)

    # Set the engine that is specific for the iSIM
    from isim_control.ni import live, acquisition, devices
    isim_devices = devices.NIDeviceGroup(settings=settings)
    acq_engine = acquisition.AcquisitionEngine(mmc, isim_devices, settings)
    acq_engine.start_xy_position = mmc.getXYPosition()
    acq_engine.use_filter_wheel = False
    acq_engine.previous_exposure = settings['exposure_time']*1000
    acq_engine.eda = True
    acq_engine.use_hardware_sequencing = False
    acq_engine.update_settings(settings)
    acq_engine.adjust_camera_exposure(settings['camera']['exposure']*1000)
    isim_devices.update_settings(settings)
    mmc.mda.set_engine(acq_engine)


    # Adaptive in process writer
    from pymmcore_eda.writer import AdaptiveWriter
    from pathlib import Path
    loc = Path("C:/Users/stepp/Desktop/MyOME.ome.zarr")
    writer = AdaptiveWriter(path=loc, delete_existing=True)
    mmc.mda.events.sequenceStarted.connect(writer.sequenceStarted)
    mmc.mda.events.sequenceFinished.connect(writer.sequenceFinished)
    mmc.mda.events.frameReady.connect(writer.frameReady)
    from pymmcore_eda.event_hub import EventHub
    EventHub(mmc.mda, writer)


    CHANNELS = ("488", "LED")
    # Viewer
    from pymmcore_eda._eda_sequence import EDASequence
    from isim_control.eda._stack_viewer._datastore import QOMEZarrDatastore
    from isim_control.eda._stack_viewer import StackViewer
    eda_sequence = EDASequence(channels=CHANNELS)
    datastore = QOMEZarrDatastore(None, overwrite=True)
    datastore._mm_config = mmc.getSystemState().dict()
    mmc.mda.events.frameReady.connect(datastore.frameReady)
    viewer = StackViewer(datastore=datastore, mmcore=mmc,
                            sequence=eda_sequence, transform=(90, False, True))
    # This has to use all the axis to init the datastore correctly
    # And the maximal number of frames that can happen
    mda_sequence = MDASequence(channels=CHANNELS,
                               time_plan={'interval': 1, 'loops': 100})
    datastore.sequenceStarted(mda_sequence)
    viewer.show()

    # EDA components
    queue_manager = QueueManager(eda_sequence=eda_sequence, mmcore=mmc)

    mda_sequence = MDASequence(
        channels=[CHANNELS[0]],
        time_plan={"interval": 1, "loops": 30},
    )
    base_actuator = MDAActuator(queue_manager, mda_sequence)
    base_actuator.wait = False

    b_actuator = ButtonActuator(queue_manager)
    b_actuator.channel_name = CHANNELS[1]

    # pub = Publisher(broker.pub_queue)
    # pub.publish("gui", "acquisition_start", [True])
    mmc.run_mda(queue_manager.acq_queue_iterator)

    base_actuator.thread.start()
    b_actuator.thread.start()
    app.exec_()
    base_actuator.thread.join()
    b_actuator.thread.join()
    # broker.stop()
    # viewer.shutdown()

if __name__ == "__main__":
    main()
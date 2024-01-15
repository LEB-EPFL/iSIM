import copy
import os
import time
import multiprocessing
from isim_control.gui.dark_theme import set_dark
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Signal

from isim_control.settings_translate import save_settings, load_settings
from isim_control.pubsub import Publisher, Broker
from isim_control.runner import iSIMRunner

from isim_control.gui.main_window import iSIM_StageWidget, MainWindow
from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import StageWidget, GroupPresetTableWidget

import threading
import logging
import sys

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # def open_audit_hook(name, *args):
    #     logger.debug(f"Opening {name} with {args}")

    # sys.addaudithook(open_audit_hook)


    # os.environ['ZARR_V3_EXPERIMENTAL_API'] = "1"

    monogram = False
    app = QApplication([])
    set_dark(app)

    broker = Broker()

    mmc = CMMCorePlus.instance()
    #This is hacky, might just want to make our own preview
    events_class = mmc.events.__class__
    new_cls = type(
        events_class.__name__, events_class.__bases__,
        {**events_class.__dict__, 'liveFrameReady': Signal(object, object, dict)},
    )
    mmc.events.__class__ = new_cls

    settings = load_settings()


    from isim_control.io.keyboard import KeyboardListener
    # key_listener = KeyboardListener(mmc=mmc)

    try:
        mmc.loadSystemConfiguration("C:/iSIM/iSIM/mm-configs/pymmcore_plus.cfg")
        mmc.setCameraDevice("PrimeB_Camera")
        mmc.setProperty("PrimeB_Camera", "TriggerMode", "Edge Trigger")
        mmc.setProperty("PrimeB_Camera", "ReadoutRate", "100MHz 16bit")
        mmc.setProperty("Sapphire", "State", 1)
        mmc.setProperty("Quantum_561nm", "Laser Operation", "On")
        mmc.setProperty("MCL NanoDrive Z Stage", "Settling time (ms)", 30)
        mmc.setXYStageDevice("MicroDrive XY Stage")
        mmc.setExposure(settings['camera']['exposure']*1000)
        mmc.setAutoShutter(False)

        #Backend
        from isim_control.ni import live, acquisition, devices
        isim_devices = devices.NIDeviceGroup(settings=settings)
        from isim_control.io.monogram import MonogramCC
        acq_engine = acquisition.AcquisitionEngine(mmc, isim_devices, settings)
        live_engine = live.LiveEngine(task=acq_engine.task, mmcore=mmc, settings=settings,
                                        device_group=isim_devices)
        mmc.mda.set_engine(acq_engine)

        monogram = MonogramCC(mmcore=mmc, publisher=Publisher(broker.pub_queue))
        broker.attach(monogram)
        stage = iSIM_StageWidget(mmc)
    except FileNotFoundError:
        from unittest.mock import MagicMock
        acq_engine = MagicMock()
        live_engine = MagicMock()
        isim_devices = MagicMock()
        # Not on the iSIM
        print("iSIM components could not be loaded.")
        mmc.loadSystemConfiguration()
        mmc.setProperty("Camera", "OnCameraCCDXSize", 2048)
        mmc.setProperty("Camera", "OnCameraCCDYSize", 2048)
        stage = StageWidget("XY", mmcore=mmc)


    from isim_control.gui.preview import iSIMPreview
    preview = iSIMPreview(mmcore=mmc)

    runner = iSIMRunner(mmc,
                        live_engine=live_engine,
                        acquisition_engine=acq_engine,
                        devices=isim_devices,
                        settings = settings,
                        publisher=Publisher(broker.pub_queue))
    broker.attach(runner)

    default_settings = copy.deepcopy(settings)

    #GUI
    frame = MainWindow(Publisher(broker.pub_queue), settings)
    broker.attach(frame)
    broker.attach(frame.mda_window)
    frame.update_from_settings(default_settings)

    group_presets = GroupPresetTableWidget(mmcore=mmc)
    frame.main.layout().addWidget(group_presets, 5, 0, 1, 3)
    group_presets.show() # needed to keep events alive?

    from isim_control.gui.output import OutputGUI
    output = OutputGUI(mmc, settings, broker, Publisher(broker.pub_queue))

    from isim_control.gui import position_history
    history_relay, history_broker, history_process = position_history.main_mp(mmc, output.buffered_datastore)

    key_listener = KeyboardListener(mmc=mmc)
    app.installEventFilter(key_listener)

    stage.show()
    preview.show()
    frame.show()
    app.exec_()

    # Clean things up
    history_relay.pub.publish("gui", "shutdown", [])
    history_relay.pub.publish("stop", "stop", [])
    history_broker.stop()
    history_relay.sub.stop()
    history_process.join()
    logging.debug("History process closed")


    broker.stop()
    full_settings = frame.get_full_settings(runner.settings)
    save_settings(full_settings)
    output.shutdown()
    logging.debug("Output GUI closed")

    mmc.setXYPosition(0, 0)
    if monogram:
        monogram.stop()
    logging.debug("App closed")
    # Not sure why we need this. No more brokers or subscribers are running at this point
    # There are active QueueFeederThreads that are spawned by the multiprocessing.Queues,
    # But those are al daemons, so they should be cleaned up when the main thread exits
    os._exit(os.EX_OK)
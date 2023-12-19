import copy
from isim_control.gui.dark_theme import set_dark
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Signal
from qtpy import QtGui

from isim_control.settings_translate import save_settings, load_settings
from isim_control.pubsub import Publisher, Broker
from isim_control.runner import iSIMRunner
from isim_control.ni import live, acquisition, devices

from isim_control.gui.main_window import iSIM_StageWidget, MainWindow
from pymmcore_plus import CMMCorePlus
from pymmcore_widgets import StageWidget, GroupPresetTableWidget


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
    isim_devices = devices.NIDeviceGroup(settings=settings)
    from isim_control.io.monogram import MonogramCC
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
    acq_engine = acquisition.AcquisitionEngine(mmc, isim_devices, settings)
    live_engine = live.LiveEngine(task=acq_engine.task, mmcore=mmc, settings=settings,
                                    device_group=isim_devices)
    mmc.mda.set_engine(acq_engine)

    monogram = MonogramCC(mmcore=mmc, publisher=Publisher(broker.pub_queue))
    stages = iSIM_StageWidget(mmc, key_listener=KeyboardListener(mmc=mmc))
    stages.show()
except FileNotFoundError:
    from unittest.mock import MagicMock
    acq_engine = MagicMock()
    live_engine = MagicMock()
    isim_devices = MagicMock()
    # Not on the iSIM
    print("iSIM components could not be loaded.")
    mmc.loadSystemConfiguration()
    stage = StageWidget("XY", mmcore=mmc)
    stage.show()


from isim_control.gui.preview import iSIMPreview
preview = iSIMPreview(mmcore=mmc, key_listener=KeyboardListener(mmc=mmc))
preview.show()

runner = iSIMRunner(mmc,
                    live_engine=live_engine,
                    acquisition_engine=acq_engine,
                    devices=isim_devices,
                    settings = settings,
                    publisher=Publisher(broker.pub_queue))
broker.attach(runner)

default_settings = copy.deepcopy(settings)

#GUI
frame = MainWindow(Publisher(broker.pub_queue), settings, key_listener=KeyboardListener(mmc=mmc))
broker.attach(frame)
broker.attach(frame.mda_window.save_settings)
frame.update_from_settings(default_settings)

group_presets = GroupPresetTableWidget(mmcore=mmc)
frame.main.layout().addWidget(group_presets, 5, 0, 1, 3)
group_presets.show() # needed to keep events alive?
frame.show()

from isim_control.gui.output import OutputGUI
output = OutputGUI(mmc)
broker.attach(output)

from isim_control.gui.position_history import PositionHistory
history = PositionHistory(mmc, key_listener=KeyboardListener(mmc=mmc))
history.show()

app.exec_()

# Clean things up
broker.stop()
full_settings = frame.get_full_settings(runner.settings)
save_settings(full_settings)

if monogram:
    monogram.stop()
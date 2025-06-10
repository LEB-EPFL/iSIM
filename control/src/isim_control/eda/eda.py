from isim_control.core import ISIMCore
from useq import MDASequence
from pymmcore_eda.actuator import MDAActuator
from pymmcore_eda.queue_manager import QueueManager

from qtpy.QtWidgets import QApplication

from isim_control.settings_translate import load_settings

if __name__ == "__main__":
    app = QApplication([])
    mmc = ISIMCore()
    settings = load_settings()

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
    mmc.setExposure(100)
    mmc.setAutoShutter(False)

    # Set the engine that is specific for the iSIM
    from isim_control.ni import live, acquisition, devices
    isim_devices = devices.NIDeviceGroup(settings=settings)
    acq_engine = acquisition.AcquisitionEngine(mmc, isim_devices, settings)
    mmc.mda.set_engine(acq_engine)


    from isim_control.gui.preview import iSIMPreview
    preview = iSIMPreview(mmcore=mmc)



    queue_manager = QueueManager(mmcore=mmc)

    mda_sequence = MDASequence(
        channels=["488"],
        time_plan={"interval": 0.5, "loops": 10},
    )
    base_actuator = MDAActuator(queue_manager, mda_sequence)
    base_actuator.wait = False

    mmc.run_mda(queue_manager.acq_queue_iterator)

    app.exec_()
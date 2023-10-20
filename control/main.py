from runner import iSIMRunner
from pubsub import Publisher, Broker
from pymmcore_widgets import LiveButton
from qtpy.QtWidgets import QApplication, QSpinBox, QVBoxLayout, QWidget, QPushButton, QSlider
from pymmcore_plus import CMMCorePlus
from control.ni import live, acquisition, devices
import time


def main():
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration("C:/iSIM/Micro-Manager-2.0.2/prime_only.cfg")
    mmc.setCameraDevice("Prime")
    mmc.setProperty("Prime", "TriggerMode", "Edge Trigger")
    mmc.setProperty("Prime", "ReadoutRate", "100MHz 16bit")
    mmc.setProperty("Sapphire", "State", 1)
    mmc.setProperty("Laser", "Laser Operation", "On")
    mmc.setAutoShutter(False)
    time.sleep(1)

    #Main communication hub
    broker = Broker()

    #Backend
    devices = devices.NIDeviceGroup()
    live_engine = live.LiveEngine(None, mmc)
    acq_engine = acquisition.AcquisitionEngine(mmc, devices)

    mmc.mda.set_engine(acq_engine)
    runner = iSIMRunner(mmc, live_engine=live_engine, acquisition_engine=acq_engine, devices=devices)
    broker.attach(runner)

    #GUI
    from pymmcore_widgets import ImagePreview
    app = QApplication([])
    gui = TestGUI(Publisher(broker.pub_queue))
    preview = ImagePreview(mmcore=mmc)
    mmc.mda.events.frameReady.connect(preview._on_image_snapped)
    preview.show()

    gui.show()
    app.exec_()


    #Teardown
    runner.stop()
    broker.stop()


class TestGUI(QWidget):
    def __init__(self, publisher):
        super().__init__()
        self.pub = publisher
        self.running = False

        self.setLayout(QVBoxLayout())
        self.fps = QSpinBox()
        self.fps.valueChanged.connect(lambda: self._on_settings_changed(['live', "fps"], self.fps.value()))
        self.fps.setValue(5)
        self.layout().addWidget(self.fps)

        self.power = QSlider()
        self.power.valueChanged.connect(lambda: self._on_settings_changed(['live', "ni", "laser_powers", "led"], self.power.value()))
        self.power.setValue(50)
        self.layout().addWidget(self.power)

        self.live_button = QPushButton("LIVE")
        self.live_button.clicked.connect(self._toggle_live_mode)
        self.live_button.setEnabled(True)
        self.layout().addWidget(self.live_button)

        self.acquisition_button = QPushButton("ACQUIRE")
        self.acquisition_button.clicked.connect(self._acquire_button)
        self.acquisition_button.setEnabled(True)
        self.layout().addWidget(self.acquisition_button)

    def _acquire_button(self):
        print("ACQUIRE")
        self.pub.publish("gui", "acquisition_button_clicked", [True])

    def _toggle_live_mode(self):
        print(self.running)
        if self.running:
            self.pub.publish("gui", "live_button_clicked", [True])
        else:
            self.pub.publish("gui", "live_button_clicked", [False])
        self.running = not self.running

    def _on_settings_changed(self, keys, value):
        self.pub.publish("gui", "settings_change", [keys, value])


if __name__ == "__main__":
    main()


from qtpy.QtWidgets import (QApplication, QPushButton, QWidget, QGridLayout, QGroupBox,
                            QRadioButton, QSpinBox, QLabel, QCheckBox, QMainWindow)
from qtpy.QtCore import Qt

from pymmcore_widgets import GroupPresetTableWidget, StageWidget
from superqt import QLabeledSlider
from isim_control.gui.dark_theme import slider_theme
from isim_control.gui.dark_theme import set_dark

from mda import iSIMMDAWidget

import pprint
import copy



class MainWindow(QMainWindow):
    def __init__(self, publisher, settings: dict = {}):
        super().__init__()
        self.setWindowTitle("MyMDA")

        self.main = QWidget()
        self.setCentralWidget(self.main)

        self.main.setLayout(QGridLayout())


        self.pub = publisher
        self.running = False

        self.settings = settings

        self.live_button = QPushButton("Live")
        self.live_button.clicked.connect(self._live)
        self.snap_button = QPushButton("Snap")
        self.mda_button = QPushButton("MDA")

        self.channelBox = QGroupBox("Live Channels")
        self.live_488 = QRadioButton("488")
        self.live_488.toggled.connect(self._488_activate)
        self.live_561 = QRadioButton("561")
        self.live_561.toggled.connect(self._561_activate)
        self.live_led = QRadioButton("LED")
        self.live_led.toggled.connect(self._led_activate)

        self.live_power_488 = QLabeledSlider(Qt.Orientation.Horizontal)
        self.live_power_488.setRange(0, 100)
        self.live_power_488.setValue(settings['live']['ni']['laser_powers']['488'])
        self.live_power_488.valueChanged.connect(self._488_value_changed)
        self.live_power_488.setDisabled(True)
        self.live_power_488.setStyleSheet(slider_theme("#00f7ff"))
        self.live_power_561 = QLabeledSlider(Qt.Orientation.Horizontal)
        self.live_power_561.setRange(0, 100)
        self.live_power_561.setValue(settings['live']['ni']['laser_powers']['561'])
        self.live_power_561.valueChanged.connect(self._561_value_changed)
        self.live_power_561.setStyleSheet(slider_theme("#c6ff00"))
        self.live_power_561.setDisabled(True)
        self.live_power_led = QLabeledSlider(Qt.Orientation.Horizontal)
        self.live_power_led.setRange(0, 100)
        self.live_power_led.setValue(settings['live']['ni']['laser_powers']['led'])
        self.live_power_led.valueChanged.connect(self._led_value_changed)
        self.live_power_led.setStyleSheet(slider_theme("#BBBBBB"))

        self.live_fps = QSpinBox()
        self.live_fps.valueChanged.connect(self.live_fps_changed)
        self.live_fps.setValue(settings['live']['fps'])
        self.live_fps.setRange(1, 10)
        self.live_fps_label = QLabel("FPS")

        self.twitchers = QCheckBox("Twitchers")
        self.twitchers.toggled.connect(self._twitchers_changed)
        self.twitchers.setChecked(settings['live']['twitchers'])

        self.setWindowTitle("MyMDA")

        self.channelBox.setLayout(QGridLayout())
        self.channelBox.layout().addWidget(self.live_488, 0, 0)
        self.channelBox.layout().addWidget(self.live_561, 1, 0)
        self.channelBox.layout().addWidget(self.live_led, 2, 0)
        self.channelBox.layout().addWidget(self.live_power_488, 0, 1)
        self.channelBox.layout().addWidget(self.live_power_561, 1, 1)
        self.channelBox.layout().addWidget(self.live_power_led, 2, 1)

        self.main.layout().addWidget(self.live_button, 0, 0,)
        self.main.layout().addWidget(self.snap_button, 1, 0)
        self.main.layout().addWidget(self.mda_button, 2, 0)

        self.main.layout().addWidget(self.live_fps_label, 0, 2)
        self.main.layout().addWidget(self.live_fps, 0, 3)
        self.main.layout().addWidget(self.twitchers, 1, 2, 1, 2)

        self.main.layout().addWidget(self.channelBox, 0, 1, 3, 1)


        self.mda_button.pressed.connect(self._mda)

        self.live_led.setChecked(True)
        self.live_power_488.installEventFilter(self)
        self.live_power_561.installEventFilter(self)
        self.live_power_led.installEventFilter(self)

    def _mda(self):
        self.mda_window = iSIMMDAWidget(settings=self.settings, publisher=self.pub)
        self.mda_window.show()

    def _488_activate(self, toggle):
        if toggle:
            self.settings['live']['channel'] = '488'
            self.live_power_488.setDisabled(False)
        else:
            self.live_power_488.setDisabled(True)
        self.pub.publish("gui", "settings_change", [['live', "channel"], self.settings['live']['channel']])

    def _488_value_changed(self, value):
        self.settings['live']['ni']['laser_powers']['488'] = value
        self.pub.publish("gui", "settings_change", [['live', "ni", "laser_powers", "488"], value])

    def _561_activate(self, toggle):
        if toggle:
            self.settings['live']['channel'] = '561'
            self.live_power_561.setDisabled(False)
        else:
            self.live_power_561.setDisabled(True)
        self.pub.publish("gui", "settings_change", [['live', "channel"], self.settings['live']['channel']])

    def _561_value_changed(self, value):
        self.settings['live']['ni']['laser_powers']['561'] = value
        self.pub.publish("gui", "settings_change", [['live', "ni", "laser_powers", "561"], value])

    def _led_activate(self, toggle):
        if toggle:
            self.settings['live']['channel'] = 'led'
            self.live_power_led.setDisabled(False)
        else:
            self.live_power_led.setDisabled(True)
        self.pub.publish("gui", "settings_change", [['live', "channel"], self.settings['live']['channel']])

    def _led_value_changed(self, value):
        self.settings['live']['ni']['laser_powers']['led'] = value
        self.pub.publish("gui", "settings_change", [['live', "ni", "laser_powers", "led"], value])

    def live_fps_changed(self, value):
        self.settings['live']['fps'] = value
        self.pub.publish("gui", "settings_change", [['live', "fps"], value])

    def _twitchers_changed(self, toggle):
        self.settings['live']['twitchers'] = toggle
        self.pub.publish("gui", "settings_change", [['live', "twitchers"], toggle])

    def _live(self):
        print(self.running)
        if self.running:
            self.pub.publish("gui", "live_button_clicked", [True])
        else:
            self.pub.publish("gui", "live_button_clicked", [False])
        self.running = not self.running

    def update_from_settings(self, settings: dict):
        self.live_power_488.setValue(settings['live']['ni']['laser_powers']['488'])
        self.live_power_561.setValue(settings['live']['ni']['laser_powers']['561'])
        self.live_power_led.setValue(settings['live']['ni']['laser_powers']['led'])
        self.live_fps.setValue(settings['live']['fps'])
        self.twitchers.setChecked(settings['live']['twitchers'])
        if settings['live']['channel'] == '488':
            self.live_488.setChecked(True)
        elif settings['live']['channel'] == '561':
            self.live_561.setChecked(True)
        else:
            self.live_led.setChecked(True)

    def eventFilter(self, obj, event):
        # Enable sliders by clicking
        sliders = [self.live_power_488, self.live_power_561, self.live_power_led]
        radios = [self.live_488, self.live_561, self.live_led]
        if event.type() == 2:
            for slider, radio in zip(sliders, radios):
                if obj == slider:
                    slider.setDisabled(False)
                    radio.setChecked(True)
                else:
                    slider.setDisabled(True)
        return super().eventFilter(obj, event)


class iSIM_StageWidget(QWidget):
    def __init__(self, mmc):
        super().__init__()
        stage1 = StageWidget("MicroDrive XY Stage", mmcore=mmc)
        stage2 = StageWidget("MCL NanoDrive Z Stage", mmcore=mmc)
        self.setLayout(QGridLayout())
        self.layout().addWidget(stage1, 2, 0)
        self.layout().addWidget(stage2, 2, 1)


if __name__ == "__main__":
    from isim_control.settings import iSIMSettings
    from isim_control.pubsub import Publisher, Broker
    from isim_control.runner import iSIMRunner
    from isim_control.ni import live, acquisition, devices
    from pymmcore_plus import CMMCorePlus
    app = QApplication([])
    set_dark(app)

    broker = Broker()

    mmc = CMMCorePlus.instance()
    settings = iSIMSettings(time_plan = {"interval": 0.2, "loops": 20},)
    settings['twitchers'] = True

    try:
        mmc.loadSystemConfiguration("C:/iSIM/iSIM/mm-configs/pymmcore_plus.cfg")
        mmc.setCameraDevice("PrimeB_Camera")
        mmc.setProperty("PrimeB_Camera", "TriggerMode", "Edge Trigger")
        mmc.setProperty("PrimeB_Camera", "ReadoutRate", "100MHz 16bit")
        mmc.setProperty("Sapphire", "State", 1)
        mmc.setProperty("Quantum_561nm", "Laser Operation", "On")
        mmc.setExposure(129)
        mmc.setAutoShutter(False)

        #Backend
        isim_devices = devices.NIDeviceGroup(settings=settings)
        acq_engine = acquisition.AcquisitionEngine(mmc, isim_devices)
        live_engine = live.LiveEngine(task = acq_engine.task, mmcore=mmc, settings=settings,
                                      device_group=isim_devices)
        mmc.mda.set_engine(acq_engine)

        runner = iSIMRunner(mmc,
                        live_engine=live_engine,
                        acquisition_engine=acq_engine,
                        devices=isim_devices,
                        settings = settings)

        broker.attach(runner)

        from pymmcore_widgets import ImagePreview
        preview = ImagePreview(mmcore=mmc)
        mmc.mda.events.frameReady.connect(preview._on_image_snapped)
        preview.show()
    except FileNotFoundError:
        # Not on the iSIM
        print("iSIM components could not be loaded.")
        mmc.loadSystemConfiguration()

    default_settings = copy.deepcopy(settings)

    #GUI
    frame = MainWindow(Publisher(broker.pub_queue), settings)
    frame.update_from_settings(default_settings)

    group_presets = GroupPresetTableWidget(mmcore=mmc)
    frame.main.layout().addWidget(group_presets, 5, 0, 1, 3)

    stages = iSIM_StageWidget(mmc)

    frame.show()
    stages.show()

    app.exec_()
    broker.stop()

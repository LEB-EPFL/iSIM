
from qtpy.QtWidgets import (QApplication, QPushButton, QWidget, QGridLayout, QGroupBox,
                            QRadioButton, QSpinBox, QLabel, QCheckBox)
from qtpy.QtCore import Qt
from pymmcore_plus import CMMCorePlus
from superqt import QLabeledSlider

from mda import iSIMMDAWidget

import pprint
import copy

mmc = CMMCorePlus()
mmc.loadSystemConfiguration()

class MainWindow(QWidget):
    def __init__(self, mmcore : CMMCorePlus = mmc, settings: dict = {}):
        super().__init__()
        self.setWindowTitle("MyMDA")
        self.setLayout(QGridLayout())

        self.mmc = mmcore
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
        self.live_power_561 = QLabeledSlider(Qt.Orientation.Horizontal)
        self.live_power_561.setRange(0, 100)
        self.live_power_561.setValue(settings['live']['ni']['laser_powers']['561'])
        self.live_power_561.valueChanged.connect(self._561_value_changed)
        self.live_power_561.setStyleSheet(
            "QSlider::handle:horizontal:enabled {background-color: green;}")
        self.live_power_561.setDisabled(True)
        self.live_power_led = QLabeledSlider(Qt.Orientation.Horizontal)
        self.live_power_led.setRange(0, 100)
        self.live_power_led.setValue(settings['live']['ni']['laser_powers']['led'])
        self.live_power_led.valueChanged.connect(self._led_value_changed)
        self.live_power_led.setStyleSheet(
            "QSlider::handle:horizontal:enabled {background-color: grey;}")

        self.live_fps = QSpinBox()
        self.live_fps.valueChanged.connect(self.live_fps_changed)
        self.live_fps.setValue(settings['live']['fps'])
        self.live_fps.setRange(1, 10)
        self.live_fps_label = QLabel("FPS")

        self.twitchers = QCheckBox("Twitchers")
        self.twitchers.toggled.connect(self._twitchers_changed)
        self.twitchers.setChecked(settings['live']['twitchers'])


        self.channelBox.setLayout(QGridLayout())
        self.channelBox.layout().addWidget(self.live_488, 0, 0)
        self.channelBox.layout().addWidget(self.live_561, 1, 0)
        self.channelBox.layout().addWidget(self.live_led, 2, 0)
        self.channelBox.layout().addWidget(self.live_power_488, 0, 1)
        self.channelBox.layout().addWidget(self.live_power_561, 1, 1)
        self.channelBox.layout().addWidget(self.live_power_led, 2, 1)

        self.layout().addWidget(self.live_button, 0, 0, 3, 1)
        self.layout().addWidget(self.snap_button, 3, 0)
        self.layout().addWidget(self.mda_button, 4, 0)

        self.layout().addWidget(self.live_fps_label, 0, 2)
        self.layout().addWidget(self.live_fps, 0, 3)
        self.layout().addWidget(self.twitchers, 1, 2, 1, 2)

        self.layout().addWidget(self.channelBox, 0, 1, 3, 1)


        self.mda_button.pressed.connect(self._mda)

        self.live_led.setChecked(True)

    def _mda(self):
        self.mda_window = iSIMMDAWidget(mmcore=self.mmc, settings=self.settings)
        self.mda_window.show()

    def _488_activate(self, toggle):
        if toggle:
            self.settings['live']['channel'] = '488'
            self.live_power_488.setDisabled(False)
        else:
            self.live_power_488.setDisabled(True)

    def _488_value_changed(self, value):
        self.settings['live']['ni']['laser_powers']['488'] = value

    def _561_activate(self, toggle):
        if toggle:
            self.settings['live']['channel'] = '561'
            self.live_power_561.setDisabled(False)
        else:
            self.live_power_561.setDisabled(True)

    def _561_value_changed(self, value):
        self.settings['live']['ni']['laser_powers']['561'] = value

    def _led_activate(self, toggle):
        if toggle:
            self.settings['live']['channel'] = 'led'
            self.live_power_led.setDisabled(False)
        else:
            self.live_power_led.setDisabled(True)

    def _led_value_changed(self, value):
        self.settings['live']['ni']['laser_powers']['led'] = value

    def live_fps_changed(self, value):
        self.settings['live']['fps'] = value

    def _twitchers_changed(self, toggle):
        self.settings['live']['twitchers'] = toggle

    def _live(self):
        pprint.pprint(self.settings)

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


if __name__ == "__main__":
    from useq import MDASequence
    app = QApplication([])

    seq = MDASequence(time_plan = {"interval": 0.2, "loops": 20},)
    settings = {}
    settings['acquisition'] = seq.model_dump()
    settings['live'] = {"channel": "561", "fps": 5, "twitchers": False}
    settings['live']['ni'] = {"laser_powers": {'488': 50, '561': 50, 'led': 100}}
    settings["ni"] = {"laser_powers": {"488": 20, "561": 50}}
    settings['twitchers'] = True
    default_settings = copy.deepcopy(settings)
    frame = MainWindow(mmc, settings)


    frame.update_from_settings(default_settings)
    frame.show()


    app.exec_()

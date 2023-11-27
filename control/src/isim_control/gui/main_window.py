from qtpy.QtWidgets import (QApplication, QPushButton, QWidget, QGridLayout, QGroupBox,
                            QRadioButton, QSpinBox, QLabel, QCheckBox, QMainWindow)
from qtpy.QtCore import Qt, Signal, QTimer

from pymmcore_widgets import GroupPresetTableWidget, StageWidget
from superqt import QLabeledSlider, fonticon
from isim_control.gui.dark_theme import slider_theme
from isim_control.gui.dark_theme import set_dark
from isim_control.gui.assets.qt_classes import QMainWindowRestore, QWidgetRestore

from isim_control.pubsub import Subscriber, Publisher
from isim_control.gui.mda import iSIMMDAWidget

import copy
from fonticon_mdi6 import MDI6


class MainWindow(QMainWindowRestore):
    def __init__(self, publisher:Publisher, settings: dict = {}):
        super().__init__()
        self.pub = publisher
        self.settings = settings

        self.main = QWidget()
        self.setCentralWidget(self.main)

        self.mda_window = iSIMMDAWidget(settings=self.settings,
                                        publisher=self.pub)

        routes = {"acquisition_finished": [lambda: self.mda_window.run_buttons._on_cancel_clicked(True)],
                  }
        self.sub = Subscriber(['gui'], routes)
        self.running = False

        self.setWindowTitle("MyMDA")
        self.main.setLayout(QGridLayout())
        self.live_button = QPushButton("Live")
        self.live_button.setIcon(fonticon.icon(MDI6.play_circle_outline, color="lime"))
        self.live_button.clicked.connect(self._live)
        self.snap_button = QPushButton("Snap")
        self.snap_button.clicked.connect(self._snap)
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

        self.exp_label = QLabel("Exposure (ms)")
        self.live_exposure = QSpinBox()
        self.live_exposure.setRange(20, 300)
        self.live_exposure.setSingleStep(10)
        self.live_exposure.setValue(settings['live']['exposure'])
        self.live_exposure.valueChanged.connect(self._live_exposure_change)

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
        self.main.layout().addWidget(self.exp_label, 2, 2, 1, 2)
        self.main.layout().addWidget(self.live_exposure, 3, 2, 1, 2)


        self.main.layout().addWidget(self.channelBox, 0, 1, 4, 1)

        self.mda_button.pressed.connect(self._mda)

        self.live_led.setChecked(True)
        self.live_power_488.installEventFilter(self)
        self.live_power_561.installEventFilter(self)
        self.live_power_led.installEventFilter(self)



    def _mda(self):
        self.mda_window.show()

    def _live_exposure_change(self, value):
        self.pub.publish("gui", "settings_change", [['live', "exposure"], value])

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
        if not self.running:
            self.pub.publish("gui", "live_button_clicked", [True])
            self.live_button.setText("Pause")
            self.live_button.setIcon(fonticon.icon(MDI6.pause_circle_outline, color="red"))
        else:
            self.pub.publish("gui", "live_button_clicked", [False])
            self.live_button.setText("Live")
            self.live_button.setIcon(fonticon.icon(MDI6.play_circle_outline, color="lime"))
        self.running = not self.running

    def _snap(self):
        self.pub.publish("gui", "snap_button_clicked", [True])
        #Limit the frequency of snaps
        self.snap_button.setDisabled(True)
        QTimer.singleShot(500, lambda: self.snap_button.setDisabled(False))

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



class iSIM_StageWidget(QWidgetRestore):
    def __init__(self, mmc):
        super().__init__()
        self.stage1 = StageWidget("MicroDrive XY Stage", mmcore=mmc)
        self.stage1._step.setValue(25)
        self.stage2 = StageWidget("MCL NanoDrive Z Stage", mmcore=mmc)
        self.stage2._step.setValue(5)
        self.stage1.snap_checkbox.setVisible(False)
        self.stage2.snap_checkbox.setVisible(False)

        self.setLayout(QGridLayout())
        self.layout().addWidget(self.stage1, 2, 0)
        self.layout().addWidget(self.stage2, 2, 1)


if __name__ == "__main__":
    # from isim_control.settings import iSIMSettings
    from isim_control.settings_translate import save_settings, load_settings
    from isim_control.pubsub import Publisher, Broker
    from isim_control.runner import iSIMRunner
    from isim_control.ni import live, acquisition, devices
    from pymmcore_plus import CMMCorePlus
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
    isim_devices = devices.NIDeviceGroup(settings=settings)

    try:
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

        monogram = MonogramCC(mmcore=mmc)
        stages = iSIM_StageWidget(mmc)
        stages.show()
    except FileNotFoundError:
        from unittest.mock import MagicMock
        acq_engine = MagicMock()
        live_engine = MagicMock()
        # Not on the iSIM
        print("iSIM components could not be loaded.")
        mmc.loadSystemConfiguration()
        stage = StageWidget("XY", mmcore=mmc)
        stage.show()

    from isim_control.gui.preview import iSIMPreview
    preview = iSIMPreview(mmcore=mmc)
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
    frame = MainWindow(Publisher(broker.pub_queue), settings)
    broker.attach(frame)
    frame.update_from_settings(default_settings)

    group_presets = GroupPresetTableWidget(mmcore=mmc)
    frame.main.layout().addWidget(group_presets, 5, 0, 1, 3)
    group_presets.show() # needed to keep events alive?
    frame.show()

    from isim_control.gui.output import OutputGUI
    output = OutputGUI(mmc)
    broker.attach(output)

    from isim_control.gui.position_history import PositionHistory
    history = PositionHistory(mmc)
    history.show()

    app.exec_()
    broker.stop()
    save_settings(runner.settings)

    if monogram:
        monogram.stop()
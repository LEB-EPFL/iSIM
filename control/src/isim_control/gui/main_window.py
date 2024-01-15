from qtpy.QtWidgets import (QPushButton, QWidget, QGridLayout, QGroupBox,
                            QRadioButton, QSpinBox, QLabel, QCheckBox, )
from qtpy.QtCore import Qt,QObject, QTimer
from qtpy import QtGui, QtCore

from pymmcore_widgets import GroupPresetTableWidget, StageWidget
from pymmcore_widgets._device_property_table import DevicePropertyTable
from superqt import QLabeledSlider, fonticon
from isim_control.gui.dark_theme import slider_theme

from isim_control.gui.assets.qt_classes import QMainWindowRestore, QWidgetRestore

from isim_control.pubsub import Subscriber, Publisher
from isim_control.gui.mda import iSIMMDAWidget

import copy
from fonticon_mdi6 import MDI6
import logging

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
                  "live_button_clicked": [self._on_live_toggle_event],
                  "laser_intensity_changed": [self._on_laser_intensity_changed],
                  "channel_activated": [self._on_channel_activated],
                  }
        self.sub = Subscriber(['gui'], routes)
        self.running = False

        self.setWindowTitle("iSIM-Manager")
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

        self.device_menu = self.menuBar().addMenu("Devices")
        self.device_prop_table = DevicePropertyTable()
        self.device_menu.addAction("Device Properties").triggered.connect(self._device_properties)

        self.main.layout().addWidget(self.channelBox, 0, 1, 4, 1)

        self.mda_button.pressed.connect(self._mda)

        self.live_led.setChecked(True)
        self.live_power_488.installEventFilter(self)
        self.live_power_561.installEventFilter(self)
        self.live_power_led.installEventFilter(self)

    def _on_channel_activated(self, channel:str):
        if channel == "488":
            obj = self.live_power_488
        elif channel == "561":
            obj = self.live_power_561
        elif channel == "led":
            obj = self.live_power_led
        sliders = [self.live_power_488, self.live_power_561, self.live_power_led]
        radios = [self.live_488, self.live_561, self.live_led]
        for slider, radio in zip(sliders, radios):
            if obj == slider:
                slider.setDisabled(False)
                radio.setChecked(True)
            else:
                slider.setDisabled(True)

    def _on_laser_intensity_changed(self, channel, value):
        if channel == 1:
            current = self.live_power_488.value()
            future = max(self.live_power_488.minimum(),
                         min([current + value, self.live_power_488.maximum()]))
            self.live_power_488.setValue(int(future))
        elif channel == 2:
            current = self.live_power_561.value()
            self.live_power_561.setValue(int(current + value))
        elif channel == 3:
            current = self.live_power_led.value()
            self.live_power_led.setValue(int(current + value))

    def _on_live_toggle_event(self, toggle):
        if toggle:
            self.live_button.setText("Pause")
            self.live_button.setIcon(fonticon.icon(MDI6.pause_circle_outline, color="red"))
            self.running = True
        else:
            self.live_button.setText("Live")
            self.live_button.setIcon(fonticon.icon(MDI6.play_circle_outline, color="lime"))
            self.running = False
        self.live_button.setDisabled(False)

    def _device_properties(self):
        if not self.device_prop_table.isVisible():
            self.device_prop_table.show()
        else:
            self.device_prop_table.hide()

    def _mda(self):
        self.mda_window.show()
        self.mda_window.raise_()

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
        self.live_button.setDisabled(True)
        if not self.running:
            self.pub.publish("gui", "live_button_clicked", [True])
        else:
            self.pub.publish("gui", "live_button_clicked", [False])
        logging.debug(f"Live button clicked{self.running}")
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

    def get_full_settings(self, settings:dict):
        mda_widget = self.mda_window.mda
        settings['acquisition']['time_plan'] = mda_widget.time_plan.value().model_dump()
        settings['acquisition']['grid_plan'] = mda_widget.grid_plan.value().model_dump()
        settings['acquisition']['z_plan'] = mda_widget.z_plan.value().model_dump()

        channels = []
        settings['use_channels'] = {}
        table = mda_widget.channels.table()
        for idx, channel in enumerate(mda_widget.channels.value(exclude_unchecked=False)):
            channels.append(channel.model_dump())
            use_channel = (table.columnInfo(table._get_selector_col()).
                           isChecked(table, idx, table._get_selector_col()))
            settings['use_channels'][channel.config] = use_channel

        channels = tuple(channels)
        settings['acquisition']['channels'] = channels
        settings['use_plan'] = {'time_plan': mda_widget.tab_wdg.isAxisUsed('t'),
                                'grid_plan': mda_widget.tab_wdg.isAxisUsed('g'),
                                'z_plan': mda_widget.tab_wdg.isAxisUsed('z'),
                                'channels': mda_widget.tab_wdg.isAxisUsed('c')}
        return settings

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

    def keyPressEvent(self, ev):
        print(ev.key())

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

from pymmcore_widgets.useq_widgets._mda_sequence import MDASequenceWidget
from isim_control.pubsub import Subscriber
from qtpy.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QCheckBox,
                            QSizePolicy, QGridLayout, QLineEdit, QPushButton)
from qtpy.QtCore import Qt

from superqt import QLabeledSlider, fonticon
from isim_control.settings_translate import useq_from_settings
from isim_control.gui.dark_theme import slider_theme
from isim_control.gui.assets.qt_classes import QWidgetRestore
from useq import Channel
from fonticon_mdi6 import MDI6

class iSIMMDAWidget(QWidgetRestore):
    def __init__(self, settings:dict, publisher, parent=None):
        super().__init__(parent=parent)
        self.mda = MDASequenceWidget()
        self.mda.tab_wdg.removeTab(self.mda.tab_wdg.indexOf(self.mda.stage_positions))
        self.mda.keep_shutter_open.hide()
        self.mda.af_axis.hide()

        self.mda.grid_plan._fov_height = 114.688
        self.mda.grid_plan._fov_width = 114.688
        self.settings = settings
        self.lasers = LaserPowers(settings)
        self.isim = iSIMSettingsWidget()
        self.save_settings = SaverWidget()
        self.save_settings.set_state(settings)
        self.pub = publisher

        self.setWindowTitle("iSIM MDA")
        self.run_buttons = RunButtons(publisher, self)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.mda)
        self.layout().addWidget(self.lasers)
        self.layout().addWidget(self.isim)
        self.layout().addWidget(self.save_settings)
        self.layout().addWidget(self.run_buttons)
        self.mda.setValue(useq_from_settings(settings))
        for key, value in settings.get('use_plan', {}).items():
            match key:
                case 'time_plan':
                    self.mda.tab_wdg.setChecked(self.mda.time_plan, value)
                case 'grid_plan':
                    self.mda.tab_wdg.setChecked(self.mda.grid_plan, value)
                case 'z_plan':
                    self.mda.tab_wdg.setChecked(self.mda.z_plan, value)
                case 'channels':
                    self.mda.tab_wdg.setChecked(self.mda.channels, value)
        table = self.mda.channels.table()
        column_info = table.columnInfo(table._get_selector_col())
        use_channels = settings.get('use_channels', {'488': True, '561': True, 'LED': False})
        for idx, (key, value) in enumerate(use_channels.items()):
            check_value = Qt.CheckState.Checked if value else Qt.CheckState.Unchecked
            match key:
                case '488':
                    column_info.setCheckState(table, idx, table._get_selector_col(), check_value)
                case '561':
                    column_info.setCheckState(table, idx, table._get_selector_col(), check_value)
                case 'LED':
                    column_info.setCheckState(table, idx, table._get_selector_col(), check_value)

        routes = {"output_ready": [self.run_buttons.activate_run_btn],
                  "acquisition_finished": [self.save_settings._increase_folder_number]}
        self.sub = Subscriber(["gui"], routes)

        # Handle same exposure for all channels
        self.last_exposures = [x['exposure'] for x
                               in self.mda.channels.table().iterRecords(exclude_unchecked=False)]
        self.mda.channels.valueChanged.connect(self._set_exposures)

    def setValue(self, settings: dict):
        seq = useq_from_settings(settings)
        self.mda.setValue(seq)
        self.isim.set_state(settings)
        self.save_settings.set_state(settings)
        self.lasers.power_488.setValue(settings['ni']['laser_powers']['488'])
        self.lasers.power_561.setValue(settings['ni']['laser_powers']['561'])
        self.lasers.power_led.setValue(settings['ni']['laser_powers']['led'])

    def get_settings(self):
        self.settings['acquisition'] = self.mda.value().model_dump()
        self.settings['ni']['laser_powers']['488'] = self.lasers.power_488.value()
        self.settings['ni']['laser_powers']['561'] = self.lasers.power_561.value()
        self.settings['ni']['laser_powers']['led'] = self.lasers.power_led.value()
        isim_settings = self.isim.get_state()
        for key,value in isim_settings:
            self.settings.set_by_path(key, value)
        save_settings = self.save_settings.get_state()
        for key,value in save_settings:
            self.settings.set_by_path(key, value)
        return self.settings

    def _set_exposures(self):
        exposures = [x['exposure'] for x
                     in self.mda.channels.table().iterRecords(exclude_unchecked=False)]
        new_exp = exposures[0]
        for exp in exposures:
            if not exp in self.last_exposures:
                new_exp = exp
        new_exp = 50 if new_exp < 50 else new_exp
        new_exp = 300 if new_exp > 300 else new_exp
        for row, data in enumerate(self.mda.channels.table().iterRecords(exclude_unchecked=False)):
            data['exposure'] = new_exp
            self.mda.channels.table().setRowData(row, data)
        self.last_exposures = [new_exp for x in range(len(exposures))]


class RunButtons(QWidget):
    def __init__(self, publisher, parent=None):
        super().__init__(parent)
        self.mda = parent
        self.pub = publisher
        self.pause = False

        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self._on_run_clicked)
        self.run_btn.setIcon(fonticon.icon(MDI6.play_circle_outline, color="lime"))
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self._on_pause_clicked)
        self.pause_btn.setIcon(fonticon.icon(MDI6.pause_circle_outline, color="green"))
        self.pause_btn.hide()
        self.cancel_btn = QPushButton("Stop")
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        self.cancel_btn.setIcon(fonticon.icon(MDI6.stop_circle_outline, color="magenta"))
        self.cancel_btn.hide()

        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self.run_btn)
        self.layout().addWidget(self.pause_btn)
        self.layout().addWidget(self.cancel_btn)

    def _on_run_clicked(self) -> None:
        self.pub.publish("gui", "settings_change", [[], self.mda.get_settings()])
        self.pub.publish("gui", "acquisition_start", [True])
        self.run_btn.hide()
        self.pause_btn.show()
        self.cancel_btn.show()
        self.pause = False

    def _on_pause_clicked(self) -> None:
        self.pause = not self.pause
        self.pub.publish("gui", "acquisition_pause", [self.pause])
        if self.pause:
            self.pause_btn.setIcon(fonticon.icon(MDI6.play_circle_outline, color="lime"))
            self.pause_btn.setText("Resume")
        else:
            self.pause_btn.setIcon(fonticon.icon(MDI6.pause_circle_outline, color="green"))
            self.pause_btn.setText("Pause")

    def _on_cancel_clicked(self, silent=False) -> None:
        if not silent:
            self.pub.publish("gui", "acquisition_cancel")
        self.run_btn.show()
        self.pause_btn.hide()
        self.pause_btn.setIcon(fonticon.icon(MDI6.pause_circle_outline, color="green"))
        self.pause_btn.setText("Pause")
        self.cancel_btn.hide()
        self.run_btn.setDisabled(True)
        self.pause = False

    def activate_run_btn(self):
        self.run_btn.setDisabled(False)


class LaserPowers(QWidget):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.power_488 = QLabeledSlider(Qt.Orientation.Horizontal)
        self.power_488.setRange(0, 100)
        self.power_488.setValue(settings['ni']['laser_powers']['488'])
        self.power_488.setStyleSheet(slider_theme("#00f7ff"))

        self.power_561 = QLabeledSlider(Qt.Orientation.Horizontal)
        self.power_561.setRange(0, 100)
        self.power_561.setValue(settings['ni']['laser_powers']['561'])
        self.power_561.setStyleSheet(slider_theme("#c6ff00"))

        self.power_led = QLabeledSlider(Qt.Orientation.Horizontal)
        self.power_led.setRange(0, 100)
        self.power_led.setValue(settings['ni']['laser_powers']['led'])
        self.power_led.setStyleSheet(slider_theme("#BBBBBB"))

        self.setLayout(QGridLayout())
        self.layout().addWidget(QLabel("488"), 0, 0)
        self.layout().addWidget(self.power_488, 0, 1)
        self.layout().addWidget(QLabel("561"), 1, 0)
        self.layout().addWidget(self.power_561, 1, 1)
        self.layout().addWidget(QLabel("LED"), 2, 0)
        self.layout().addWidget(self.power_led, 2, 1)


class iSIMSettingsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        text = """
            Settings specific to the iSIM.
        """
        self.setLayout(QGridLayout())

        self.label = QLabel(text)
        self.layout().addWidget(self.label, 0, 0, 1, 2)

        self.twitchers = QCheckBox("Twitchers")
        self.twitchers.setChecked(True)
        self.layout().addWidget(self.twitchers, 1, 0)

        self.filters = QCheckBox("Filterwheel")
        self.filters_label = QLabel("<i>This will slow down acquisition considerably</i>")
        self.filters_label.setMinimumSize(100, 10)
        self.filters_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Maximum)
        self.layout().addWidget(self.filters, 2, 0)
        self.layout().addWidget(self.filters_label, 2, 1)

    def set_state(self, settings: dict):
        self.twitchers.setChecked(settings['twitchers'])
        self.filters.setChecked(settings['use_filters'])

    def get_state(self):
        return (
            [["twitchers"], self.twitchers.isChecked()],
            [["ni", "twitchers"], self.twitchers.isChecked()],
            [["use_filters"], self.filters.isChecked()])


class SaverWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QGridLayout())
        self.save = QCheckBox("Save to:")
        self.layout().addWidget(self.save)
        self.path = QLineEdit("C:/Users/stepp/Desktop/OMETIFF_000")
        self.layout().addWidget(self.path)

    def _increase_folder_number(self):
        path = self.path.text()
        path = path.split("_")
        try:
            num = int(path[-1])
            path[-1] = str(num+1).zfill(3)
        except ValueError:
            num = 0
            path.append("000")
        path = "_".join(path)
        self.path.setText(path)

    def get_state(self):
        return (
            [["save"], self.save.isChecked()],
            [["path"], self.path.text()])

    def set_state(self, settings: dict):
        self.save.setChecked(settings['save'])
        self.path.setText(settings['path'])

if __name__ == "__main__":

    from isim_control.settings import iSIMSettings

    app = QApplication([])
    acq = iSIMSettings(
        time_plan = {"interval": 0.15, "loops": 10}
        )
    frame = iSIMMDAWidget(settings=acq)
    frame.setWindowTitle("MyMDA")

    frame.show()


    app.exec_()

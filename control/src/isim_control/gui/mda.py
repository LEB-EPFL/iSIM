from pymmcore_widgets.useq_widgets._mda_sequence import MDASequenceWidget
from qtpy.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QCheckBox,
                            QSizePolicy, QGridLayout, QTabBar, QPushButton)
from qtpy.QtCore import Qt

from superqt import QLabeledSlider
from isim_control.settings_translate import useq_from_settings
from isim_control.gui.dark_theme import slider_theme


class iSIMMDAWidget(MDASequenceWidget):
    def __init__(self, settings:dict, publisher, parent=None):
        self.settings = settings
        self.lasers = LaserPowers(settings)
        self.isim = iSIMSettingsWidget()
        self.pub = publisher
        super().__init__(parent=parent)
        self.run_buttons = RunButtons(publisher, self)
        self.layout().addWidget(self.lasers)
        self.layout().addWidget(self.isim)
        self.layout().addWidget(self.run_buttons)
        super().setValue(useq_from_settings(settings))

    def setValue(self, settings: dict):
        seq = useq_from_settings(settings)
        super().setValue(seq)
        self.isim.set_state(settings)
        self.lasers.power_488.setValue(settings['ni']['laser_powers']['488'])
        self.lasers.power_561.setValue(settings['ni']['laser_powers']['561'])

    def get_settings(self):
        self.settings['acquisition'] = super().value().model_dump()
        self.settings['ni']['laser_powers']['488'] = self.lasers.power_488.value()
        self.settings['ni']['laser_powers']['561'] = self.lasers.power_561.value()
        isim_settings = self.isim.get_state()
        for key,value in isim_settings:
            self.settings.set_by_path(key, value)
        return self.settings

class RunButtons(QWidget):
    def __init__(self, publisher, parent=None):
        super().__init__(parent)
        self.mda = parent
        self.pub = publisher
        self.run_button = QPushButton("Run")
        self.run_button.clicked.connect(self._on_run_clicked)
        self.setLayout(QHBoxLayout())
        self.layout().addWidget(self.run_button)

    def _on_run_clicked(self) -> None:
        self.pub.publish("gui", "settings_change", [[], self.mda.get_settings()])
        self.pub.publish("gui", "acquisition_button_clicked", [True])

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

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.power_488)
        self.layout().addWidget(self.power_561)


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

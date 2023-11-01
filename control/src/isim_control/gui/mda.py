from pymmcore_widgets.mda._core_mda import MDAWidget
from qtpy.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QCheckBox, QSizePolicy,
                            QGridLayout)
from qtpy.QtCore import Qt
from pymmcore_plus import CMMCorePlus
from superqt import QLabeledSlider
import pprint
from isim_control.settings_translate import useq_from_settings

# mmc = CMMCorePlus()
# mmc.loadSystemConfiguration()


class iSIMMDAWidget(MDAWidget):
    def __init__(self, settings:dict, publisher, parent=None):
        self.settings = settings
        self.lasers = LaserPowers(settings)
        self.isim = iSIMSettingsTab()
        self.pub = publisher
        super().__init__(parent=parent)
        self.tab_wdg.channels.layout().addWidget(self.lasers)
        self.tab_wdg.addTab(self.isim, "iSIM", checked=True)
        self.tab_wdg._cboxes[-1].hide()
        self.tab_wdg.setCurrentIndex(self.tab_wdg.indexOf(self.tab_wdg.channels))
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
        for key,value in isim_settings.items():
            self.settings[key] = value
        return self.settings

    def _on_run_clicked(self) -> None:
        pprint.pprint(self.get_settings())
        self.pub.publish("gui", "acquisition_button_clicked", [True])


class LaserPowers(QWidget):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.power_488 = QLabeledSlider(Qt.Orientation.Horizontal)
        self.power_488.setRange(0, 100)
        self.power_488.setValue(settings['ni']['laser_powers']['488'])
        self.power_561 = QLabeledSlider(Qt.Orientation.Horizontal)
        self.power_561.setRange(0, 100)
        self.power_561.setValue(settings['ni']['laser_powers']['561'])
        self.power_561.setStyleSheet(
            "QSlider::handle:horizontal:enabled {background-color: green;}")

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.power_488)
        self.layout().addWidget(self.power_561)


class iSIMSettingsTab(QWidget):
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
        return {
            "twitchers": self.twitchers.isChecked(),
            "use_filters": self.filters.isChecked(),
        }


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

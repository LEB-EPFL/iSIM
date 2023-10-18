from pymmcore_widgets.mda._core_mda import MDAWidget
from qtpy.QtWidgets import (QApplication, QPushButton, QWidget, QCheckBox, QSpinBox, QLabel,
                            QVBoxLayout)
from qtpy.QtCore import Qt
from pymmcore_plus import CMMCorePlus
from superqt import QLabeledSlider
from useq import MDASequence

mmc = CMMCorePlus()
mmc.loadSystemConfiguration()


class iSIMMDAWidget(MDAWidget):
    def __init__(self, mmcore:CMMCorePlus, settings:dict, parent=None):
        self.settings = settings
        self.lasers = LaserPowers(settings)
        self.twitchers = TwitcherSettings()
        super().__init__(mmcore=mmc, parent=parent)
        self.tab_wdg.channels.layout().addWidget(self.lasers)
        self.tab_wdg.addTab(self.twitchers, "Twitchers", checked=settings['twitchers'])
        self.tab_wdg.setCurrentIndex(self.tab_wdg.indexOf(self.tab_wdg.channels))

    def setValue(self, settings: dict):
        seq = MDASequence(**settings['acquisition'])
        super().setValue(seq)
        self.tab_wdg.setTabEnabled(self.tab_wdg.indexOf(self.twitchers), settings['twitchers'])
        self.lasers.power_488.setValue(settings['ni']['laser_powers']['488'])
        self.lasers.power_561.setValue(settings['ni']['laser_powers']['561'])

    def settings(self):
        settings['acquisition'] = super().value()
        settings['ni']['laser_powers']['488'] = self.lasers.power_488.value()
        settings['ni']['laser_powers']['561'] = self.lasers.power_561.value()
        settings['twitchers'] = self.tab_wdg.isTabEnabled(self.tab_wdg.indexOf(self.twitchers))
        return settings


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


class TwitcherSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # self.on_off = QCheckBox("Use Twitchers")
        text = """
        Twitchers will be run with the default settings for optimized performance

        These settings can be found directly in the device settings

        """
        self.label = QLabel(text)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.label)
        # self.frequency_label = QLabel("Frequency")
        # self.frequency = QSpinBox()

        # self.amplitude_label = QLabel("Amplitude")
        # self.amplitude = QSpinBox()



if __name__ == "__main__":

    app = QApplication([])

    settings = {"ni": {"laser_powers": {"488": 20, "561": 50}}}
    settings['twitchers'] = True

    frame = iSIMMDAWidget(mmcore=mmc, settings=settings)
    frame.setWindowTitle("MyMDA")

    frame.show()


    app.exec_()
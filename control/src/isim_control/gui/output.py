from pymmcore_plus import CMMCorePlus
from pymmcore_widgets._mda._stack_viewer import StackViewer
from pymmcore_widgets._mda._datastore import QLocalDataStore
from useq import MDASequence

from isim_control.settings import iSIMSettings
from isim_control.settings_translate import useq_from_settings
from isim_control.pubsub import Subscriber
from isim_control.io.ome_tiff_writer import OMETiffWriter

from qtpy.QtCore import QObject, Signal, QTimer
import time


class OutputGUI(QObject):
    acquisition_started = Signal()
    def __init__(self, mmcore: CMMCorePlus):
        super().__init__()
        self.mmc = mmcore

        routes = {"acquisition_start": [self._on_acquisition_start],
                  "settings_change": [self._on_settings_change],
                  "live_button_clicked": [self._on_live_toggle],}
        self.sub = Subscriber(["gui"], routes)
        self.settings = iSIMSettings()
        self.acquisition_started.connect(self.make_viewer)
        self.last_live_stop = time.perf_counter()

    def _on_settings_change(self, keys, value):
        self.settings.set_by_path(keys, value)

    def _on_acquisition_start(self, toggled):
        self.acquisition_started.emit()

    def make_viewer(self):
        sequence: MDASequence = useq_from_settings(self.settings)
        sizes = sequence.sizes
        shape = [sizes.get('t', 1),
                    sizes.get('z', 1),
                    sizes.get('c', 1),
                    self.mmc.getImageHeight(),
                    self.mmc.getImageWidth()]
        self.datastore = QLocalDataStore(shape, mmcore=self.mmc)
        if self.settings['save']:
            self.writer = OMETiffWriter(self.settings['path'])
            self.writer.sequenceStarted(sequence)
            self.mmc.mda.events.frameReady.connect(self.writer.frameReady)
        # Delay the creation of the viewer so that the preview can finish
        self.size = (self.mmc.getImageHeight(), self.mmc.getImageWidth())
        delay = int(max(0, 1200 - (time.perf_counter() - self.last_live_stop)*1000))
        self.timer = QTimer.singleShot(delay, self.create_viewer)
        # print("Delaying viewer creation by", delay, "ms")

    def create_viewer(self):
        self.viewer = StackViewer(datastore=self.datastore, mmcore=self.mmc,
                                  sequence=useq_from_settings(self.settings),
                                  size=self.size)
        self.viewer.show()

    def _on_live_toggle(self, toggled):
        if not toggled:
            self.last_live_stop = time.perf_counter()
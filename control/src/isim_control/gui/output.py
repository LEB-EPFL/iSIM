from pymmcore_plus import CMMCorePlus
from pymmcore_widgets._mda._stack_viewer import StackViewer
from pymmcore_widgets._mda._datastore import QLocalDataStore
from useq import MDASequence

from isim_control.settings import iSIMSettings
from isim_control.settings_translate import useq_from_settings
from isim_control.pubsub import Subscriber
from isim_control.io.ome_tiff_writer import OMETiffWriter

from qtpy.QtCore import QObject, Signal




class OutputGUI(QObject):
    acquisition_started = Signal()
    def __init__(self, mmcore: CMMCorePlus):
        super().__init__()
        self.mmc = mmcore

        routes = {"acquisition_start": [self._on_acquisition_start],
                  "settings_change": [self._on_settings_change]}
        self.sub = Subscriber(["gui"], routes)
        self.settings = iSIMSettings()
        self.acquisition_started.connect(self.make_viewer)

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
        self.viewer = StackViewer(datastore=self.datastore, mmcore=self.mmc,
                                  sequence=useq_from_settings(self.settings))
        self.viewer.show()
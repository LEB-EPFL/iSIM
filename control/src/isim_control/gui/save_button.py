from pathlib import Path
import numpy as np

from qtpy.QtWidgets import QPushButton, QWidget, QFileDialog
from qtpy.QtGui import QCloseEvent
from qtpy.QtCore import QSize
from fonticon_mdi6 import MDI6
from superqt import QLabeledSlider, fonticon
from useq import MDAEvent, MDASequence
from pymmcore_widgets._mda._datastore import QLocalDataStore

from isim_control.io.ome_tiff_writer import OMETiffWriter
from isim_control.settings_translate import load_settings, save_settings


class SaveButton(QPushButton):
    def __init__(self,
                 datastore:QLocalDataStore,
                 seq: MDASequence|None = None,
                 settings: dict | None = None,
                 mm_config: str | None = None,
                 parent: QWidget | None = None):

        super().__init__(parent=parent)
        # self.setFont(QFont('Arial', 50))
        self.setMinimumHeight(40)
        self.setIcon(fonticon.icon(MDI6.content_save_outline, color="gray"))
        self.setIconSize(QSize(30, 30))
        self.setFixedSize(40, 40)
        self.clicked.connect(self.on_click)
        settings = load_settings("stack_view")
        self.save_loc = settings.get("path", Path.home())
        self.datastore = datastore
        self.seq = seq
        self.settings = settings
        self.mm_config = mm_config

    def on_click(self):
        self.save_loc, _ = QFileDialog.getSaveFileName(directory=self.save_loc)
        saver = OMETiffWriter(self.save_loc, self.settings, self.mm_config)
        shape = self.datastore.array.shape
        indeces = np.stack(np.meshgrid(range(shape[0]),
                                       range(shape[1]),
                                       range(shape[2]),
                                       range(shape[3])), -1).reshape(-1, 4)
        for index in indeces:
            event_index = {'t': index[0], 'z': index[1], 'c': index[2], 'g': index[3]}
            #TODO: we should also save the event info in the datastore and the metadata.
            saver.frameReady(self.datastore.array[*index], MDAEvent(index=event_index, sequence=self.seq), {})

    def __del__(self):
        settings = {"path": str(self.save_loc)}
        save_settings(settings, "stack_view")

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        settings = {"path": str(self.save_loc)}
        save_settings(settings, "stack_view")
        return super().closeEvent(a0)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication
    from pymmcore_plus import CMMCorePlus
    from useq import MDASequence
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()

    app = QApplication([])

    seq = MDASequence(time_plan={"interval":0.01, "loops": 10},
                      z_plan={"range": 3, "step": 1},
                      channels=[{"config": "DAPI", "exposure": 1},
                                {"config": "FITC", "exposure": 1}])
    shape = [seq.sizes.get('t', 1),
             seq.sizes.get('z', 1),
             seq.sizes.get('c', 1),
             mmc.getImageHeight(),
             mmc.getImageWidth()]
    datastore = QLocalDataStore(shape, mmcore=mmc)
    mmc.run_mda(seq)
    widget = SaveButton(datastore, seq)
    widget.show()
    app.exec_()
from qtpy.QtWidgets import QPushButton, QFileDialog, QWidget
from qtpy.QtCore import QSize
from superqt import fonticon
from isim_control.io.ome_tiff_writer import OMETiffWriter
from useq import MDASequence, MDAEvent

from .._datastore import QLocalDataStore
from fonticon_mdi6 import MDI6
from pathlib import Path
import numpy as np

class SaveButton(QPushButton):
    def __init__(self,
                 datastore:QLocalDataStore,
                 seq: MDASequence|None = None,
                 parent: QWidget | None = None):

        super().__init__(parent=parent)
        # self.setFont(QFont('Arial', 50))
        self.setMinimumHeight(40)
        self.setIcon(fonticon.icon(MDI6.content_save_outline, color="gray"))
        self.setIconSize(QSize(30, 30))
        self.setFixedSize(40, 40)
        self.clicked.connect(self.on_click)
        self.save_loc = Path.home()
        self.datastore = datastore
        self.seq = seq

    def on_click(self):
        self.save_loc, _ = QFileDialog.getSaveFileName(directory=self.save_loc)
        saver = OMETiffWriter(self.save_loc)
        shape = self.datastore.array.shape
        indeces = np.stack(np.meshgrid(range(shape[0]),
                                       range(shape[1]),
                                       range(shape[2]),
                                       range(shape[3])), -1).reshape(-1, 4)
        for index in indeces:
            event_index = {'t': index[0], 'z': index[1], 'c': index[2], 'g': index[3]}
            #TODO: we should also save the event info in the datastore and the metadata.
            saver.frameReady(self.datastore.array[*index], MDAEvent(index=event_index, sequence=self.seq), {})
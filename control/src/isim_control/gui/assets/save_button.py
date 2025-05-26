from pathlib import Path
import warnings

from qtpy.QtWidgets import  QWidget, QFileDialog
from qtpy.QtGui import QCloseEvent
from pymmcore_plus import CMMCorePlus
from useq import  MDASequence
import zarr

from isim_control.io.ome_tiff_writer import OMETiffWriter
from isim_control.io.datastore import QOMEZarrDatastore


from qtpy.QtCore import QSize
from qtpy.QtGui import QCloseEvent
from qtpy.QtWidgets import QFileDialog, QPushButton, QWidget
from superqt import fonticon
from fonticon_mdi6 import MDI6




class CoreSaveButton(QPushButton):
    def __init__(
        self,
        datastore: QOMEZarrDatastore,
        parent: QWidget | None = None,
    ):
        super().__init__(parent=parent)
        # self.setFont(QFont('Arial', 50))
        # self.setMinimumHeight(30)
        self.setIcon(fonticon.icon(MDI6.content_save_outline, color="gray"))
        self.setIconSize(QSize(25, 25))
        self.setFixedSize(30, 30)
        self.clicked.connect(self._on_click)

        self.datastore = datastore
        self.save_loc = Path.home()

    def _on_click(self) -> None:
        self.save_loc, _ = QFileDialog.getSaveFileName(directory=str(self.save_loc))
        if self.save_loc:
            self._save_as_zarr(self.save_loc)

    def _save_as_zarr(self, save_loc: str | Path) -> None:
        dir_store = zarr.DirectoryStore(save_loc)
        zarr.copy_store(self.datastore._group.attrs.store, dir_store)

    def closeEvent(self, a0: QCloseEvent | None) -> None:
        super().closeEvent(a0)


class SaveButton(CoreSaveButton):
    def __init__(self,
                 datastore:QOMEZarrDatastore,
                 mmcore: CMMCorePlus|None = None,
                 parent: QWidget | None = None):
        super().__init__(datastore, parent=parent)
        self.mm_config = None
        self.settings = None
        self.save_loc = Path.home()
        self.current_sequence: None | MDASequence = None

        if mmcore:
            self._mmc = mmcore
            self._mmc.mda.events.sequenceStarted.connect(self.sequenceStarted)

    def sequenceStarted(self, sequence: MDASequence, mm_config:dict, settings:dict) -> None:
        self.mm_config = mm_config
        self.settings = settings
        self.save_loc = Path(settings['path']).parent
        self.current_sequence = sequence
        self._used_axes = tuple(sequence.used_axes)

    def _on_click(self) -> None:
        self.save_loc, _ = QFileDialog.getSaveFileName(directory=str(self.save_loc))
        if Path(self.save_loc).suffix == ".zarr":
            super()._save_as_zarr(self.save_loc)
        elif Path(self.save_loc).suffix == ".tiff":
            extensions = "".join(Path(self.save_loc).suffixes)
            try:
                mm_config=self._mmc.getSystemState().dict()
            except AttributeError:
                print("Can't load mmconfig, using empty dict")
                mm_config=self.mm_config
            saver = OMETiffWriter(str(self.save_loc).removesuffix(extensions),
                                  self.datastore,
                                  #TODO: don't call _mmc here if mm_config was passed in
                                  mm_config=mm_config,
                                  settings=self.settings)
            for event in self.current_sequence.iter_events():
                #TODO: we should also save the event info in the datastore and the metadata.
                saver.frameReady(event)
        else:
            warnings.warn(f"Unknown file extension {Path(self.save_loc).suffix}")


    def closeEvent(self, a0: QCloseEvent | None) -> None:
        return super().closeEvent(a0)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication
    from pymmcore_plus import CMMCorePlus
    from useq import MDASequence
    from pymmcore_widgets._mda._datastore import QOMEZarrDatastore
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()

    app = QApplication([])
    seq = MDASequence(time_plan={"interval":0.01, "loops": 10},
                      z_plan={"range": 3, "step": 1},
                      channels=[{"config": "DAPI", "exposure": 1},
                                {"config": "FITC", "exposure": 1}])
    datastore = QOMEZarrDatastore()
    mmc.mda.events.sequenceStarted.connect(datastore.sequenceStarted)
    mmc.mda.events.frameReady.connect(datastore.frameReady)

    widget = SaveButton(datastore, mmc)
    mmc.run_mda(seq)
    widget.show()
    app.exec_()
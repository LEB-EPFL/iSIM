from pathlib import Path
import warnings

from qtpy.QtWidgets import  QWidget, QFileDialog


from qtpy.QtGui import QCloseEvent
from pymmcore_plus import CMMCorePlus
from useq import  MDASequence


from isim_control.io.ome_tiff_writer import OMETiffWriter
from pymmcore_widgets._mda._datastore import QOMEZarrDatastore
from pymmcore_widgets._mda._util._save_button import SaveButton

class SaveButton(SaveButton):
    def __init__(self,
                 datastore:QOMEZarrDatastore,
                 mmcore: CMMCorePlus,
                 #TODO: add option to pass settings and mm_config
                 parent: QWidget | None = None):
        super().__init__(datastore, parent=parent)

        self.save_loc = Path.home()
        self.current_sequence: None | MDASequence = None

        if mmcore:
            self._mmc = mmcore
            self._mmc.mda.events.sequenceStarted.connect(self.sequenceStarted)

    def sequenceStarted(self, sequence: MDASequence) -> None:
        self.current_sequence = sequence
        self._used_axes = tuple(sequence.used_axes)

    def _on_click(self) -> None:
        self.save_loc, _ = QFileDialog.getSaveFileName(directory=str(self.save_loc))
        if Path(self.save_loc).suffix == ".zarr":
            super()._save_as_zarr(self.save_loc)
        elif Path(self.save_loc).suffix == ".tiff":
            extensions = "".join(Path(self.save_loc).suffixes)

            saver = OMETiffWriter(str(self.save_loc).removesuffix(extensions),
                                  self.datastore,
                                  #TODO: don't call _mmc here if mm_condfig was passed in
                                  mm_config=self._mmc.getSystemState().dict())
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
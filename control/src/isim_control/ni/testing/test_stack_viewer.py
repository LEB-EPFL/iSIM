from pymmcore_widgets._mda._stack_viewer import StackViewer
from pymmcore_widgets._mda._datastore import QLocalDataStore
from pymmcore_plus import CMMCorePlus

from qtpy.QtWidgets import QApplication

from isim_control.settings import iSIMSettings
from isim_control.settings_translate import useq_from_settings


app = QApplication([])

mmc = CMMCorePlus.instance()
mmc.loadSystemConfiguration()
datastore = QLocalDataStore(shape=(10,1,1,512,512), mmcore=mmc)


acq = iSIMSettings(
    time_plan = {"interval": 0, "loops": 10}
    )

seq = useq_from_settings(acq)


canvas = StackViewer(datastore=datastore, mmcore=mmc)
canvas.show()

mmc.run_mda(seq)

app.exec_()
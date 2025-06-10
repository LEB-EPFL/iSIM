"""This works, but did not work in our full iSIM env for some reason"""


from useq import MDASequence
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import mda_listeners_connected
from qtpy.QtWidgets import QApplication
from qtpy import QtCore, QtWidgets
from pymmcore_widgets._mda._datastore import QLocalDataStore
import time


mmc = CMMCorePlus()
class MyProcessor(QtWidgets.QWidget):
    def __init__(self, mmc):
        super().__init__()
        self.n_channels = 0
        self.mmc = mmc
    # grab info about the full experiment at the beginning

    def frameReady(self, frame, event):
        # if not using the sequenceStarted method
        if event.sequence:
            # grab info from event.sequence
            self.n_channels = len(event.sequence.channels)

    def make_datastore(self, shape):
        self.datastore = QLocalDataStore(shape)

class Starter(QtWidgets.QWidget):
    def __init__(self, mmc, processor):
        super().__init__()
        self.mmc = mmc
        self.processor = processor

    def start_acq(self):
        with mda_listeners_connected(self.processor.datastore):
            self.mmc.run_mda(self.seq)
            while self.mmc.isSequenceRunning():
                time.sleep(0.1)


app = QApplication([])


processor = MyProcessor(mmc)
processor.make_datastore((1, 1, 1, 1, 512, 512))
mmc.loadSystemConfiguration()
seq = MDASequence(axis_order="gtc",time_plan={"interval": 1, "loops": 5},channels=[{"config": "DAPI", "exposure": 1}])

starter = Starter(mmc, processor)
# processor = MyProcessor()
starter.seq = seq
QtCore.QTimer.singleShot(3, starter.start_acq)

print("Setup finished running app")

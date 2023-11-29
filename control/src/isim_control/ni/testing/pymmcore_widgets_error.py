from pymmcore_widgets import StageWidget
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import QObject

mmc = CMMCorePlus()
app = QApplication([])

mmc.loadSystemConfiguration("C:/iSIM/iSIM/mm-configs/pymmcore_plus.cfg")
widget = StageWidget("MicroDrive XY Stage")
widget.show()

class EventReceiver(QObject):
    def __init__(self, mmc):
        super().__init__()
        self.mmc = mmc
        self.mmc.events.XYStagePositionChanged.connect(self.property)

    def property(self, stage, pos):
        print("new_pos", stage, pos)

event_receiver = EventReceiver(mmc)
app.exec_()

# Problem with axis_order gtc not respecting interval  for later grid positions
from useq import MDASequence
seq = MDASequence(axis_order="gtc",time_plan={"interval": 0.1, "loops": 2},channels=[{"config": "DAPI", "exposure": 1}],grid_plan={"rows": 2, "columns": 2})

# Problem with overlaps not implemented
seq = MDASequence(grid_plan={"rows": 2, "columns": 2, "overlap": (0.2, 0.2)})

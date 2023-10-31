from qtpy.QtWidgets import QApplication
from _simple_mda import SimpleMDAWidget
from pymmcore_plus import CMMCorePlus

from useq._time import timedelta
from useq import MDASequence, TIntervalLoops, ZAboveBelow

mmc = CMMCorePlus().instance()
mmc.loadSystemConfiguration()

if __name__ == "__main__":
    app = QApplication([])
    frame = SimpleMDAWidget()
    frame.show()
    sequence = MDASequence(time_plan={"interval": 2, "loops": 50},
                           z_plan={"range": 100, "step": 0.5},
                           channels=[{"config": "488"}])
    frame.set_state(sequence)
    frame.get_state()
    app.exec_()
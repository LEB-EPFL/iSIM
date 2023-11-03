from pymmcore_widgets import GroupPresetTableWidget
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

mmc = CMMCorePlus.instance()

app = QApplication([])
widget = GroupPresetTableWidget()

mmc.loadSystemConfiguration('MMConfig_demo.cfg')

widget.show()
app.exec_()
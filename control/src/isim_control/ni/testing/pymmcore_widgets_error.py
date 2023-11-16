from pymmcore_widgets import GroupPresetTableWidget
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication, QWidget

mmc = CMMCorePlus()

mmc.events.configSet.connect(lambda: print("config"))
mmc.events.propertyChanged.connect(lambda: print("property"))

app = QApplication([])
widget = GroupPresetTableWidget(mmcore=mmc)



mmc.loadSystemConfiguration('MMConfig_demo.cfg')

widget.show()
app.exec_()
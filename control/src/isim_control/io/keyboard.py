from qtpy import QtCore, QtWidgets
from pymmcore_plus import CMMCorePlus

class KeyboardListener(QtCore.QObject):
    def __init__(self, parent = None, mmc: CMMCorePlus | None = None):
        super().__init__(parent)
        self._mmc = mmc or CMMCorePlus()

    def eventFilter(self, obj, event):
        #Check if it's a key event
        if not event.type() == 51:
            return False
        size_adjust = 10
        fov = (114/size_adjust, 114/size_adjust)
        if event.modifiers() & QtCore.Qt.ControlModifier:
            move_modifier = 0.2 * size_adjust
        elif  event.modifiers() & QtCore.Qt.ShiftModifier:
            move_modifier = 0.05 * size_adjust
        else:
            move_modifier = 1 * size_adjust
        match event.key():
            case 16777236:
                self._mmc.setRelativeXYPosition(self._mmc.getXYStageDevice(), fov[0] * move_modifier, 0)
                return True
            case 16777234:
                self._mmc.setRelativeXYPosition(self._mmc.getXYStageDevice(), - fov[0] * move_modifier, 0)
                return True
            case 16777235:
                self._mmc.setRelativeXYPosition(self._mmc.getXYStageDevice(), 0, fov[1] * move_modifier)
                return True
            case 16777237:
                self._mmc.setRelativeXYPosition(self._mmc.getXYStageDevice(), 0, - fov[1] * move_modifier)
                return True
        return False

if __name__ == "__main__":
    from qtpy import QtWidgets
    from pymmcore_plus import CMMCorePlus
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()

    from pymmcore_widgets import StageWidget

    app = QtWidgets.QApplication([])
    listener = StageWidget('XY', mmcore=mmc)
    listener.keyPressEvent = keyPressEvent.__get__(listener, StageWidget)
    listener.show()
    app.exec()
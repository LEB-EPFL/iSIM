from qtpy import QtCore, QtWidgets, QtGui
from pymmcore_plus import CMMCorePlus
from isim_control.pubsub import Publisher
import warnings


class KeyboardListener(QtCore.QObject):
    def __init__(self, parent = None, mmc: CMMCorePlus | None = None,
                 device:str = "XY", pub_queue = None):
        super().__init__(parent)
        self._mmc = mmc
        self.pub_queue = pub_queue
        if mmc:
            self.device = self._mmc.getXYStageDevice()
        elif pub_queue:
            self.pub = Publisher(pub_queue)
            self.device = device
        else:
            warnings.warn("No mmc or publisher provided, no commands will be sent")

    def _set_relative_xy_position(self, device, x, y):
        if self._mmc:
            self._mmc.setRelativeXYPosition(device, x, y)
        elif self.pub_queue:
            self.pub.publish("control", "set_relative_xy_position", [device, x, y])
        else:
            print("KeyboardListener does not have a way to publish commands")

    def eventFilter(self, obj, event):
        #Check if it's a key event
        if not isinstance(event, QtGui.QKeyEvent):
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
                if event.type() == 51:
                    self._set_relative_xy_position(self.device, fov[0] * move_modifier, 0)
                return True
            case 16777234:
                if event.type() == 51:
                    self._set_relative_xy_position(self.device, - fov[0] * move_modifier, 0)
                return True
            case 16777235:
                if event.type() == 51:
                    self._set_relative_xy_position(self.device, 0, fov[1] * move_modifier)
                return True
            case 16777237:
                if event.type() == 51:
                    self._set_relative_xy_position(self.device, 0, - fov[1] * move_modifier)
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
from pymmcore_plus import CMMCorePlus
import operator, time
import numpy as np

from qtpy import QtCore, QtGui, QtWidgets

class Colors(object):
    """ Defines colors for easy access in all widgets. """
    def __init__(self):
        self.blue = QtGui.QColor(25, 180, 210, alpha=150)
        self.red = QtGui.QColor(220, 20, 60, alpha=150)


class PositionHistory(QtWidgets.QGraphicsView):
    """ This is a widget that records the history of where the stage of the microscope has
    been for the given sample. It visualizes the time spent at a specific position on a grid
    with rectangles that get brighter for the more time spent at a position. This is also
    dependent on if the laser light was on at the given time."""
    xy_stage_position_python = QtCore.Signal(object)
    increase_values_signal = QtCore.Signal(object, object, object)

    def __init__(self, mmcore: CMMCorePlus, parent:QtWidgets.QWidget=None):
        super().__init__()
        self.mmc = mmcore

        # Set the properties for the window so that everything is shown and we don't have Scrollbars
        self.view_size = (3000, 3000)
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setBaseSize(self.view_size[0], self.view_size[1])
        self.setSceneRect(0, 25, self.view_size[0], self.view_size[1] - 50)
        self.scale(-1, -1)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Initialize the position of the stage and the parameters
        self.stage_pos = [0, 0]
        self.size_adjust = 10
        self.fov_size = (114/self.size_adjust, 114/self.size_adjust)
        self.sample_size = self.view_size
        pos = self.rectangle_pos(self.stage_pos)

        # Get the components of the GUI ready
        self.map = QtGui.QImage(self.sample_size[0], self.sample_size[1],
                                QtGui.QImage.Format.Format_RGB32)

        self.my_pixmap = self.scene().addPixmap(QtGui.QPixmap.fromImage(self.map))
        self.my_pixmap.setZValue(-100)
        self.fitInView()

        # Circle giving relation to coverslip
        diameter = self.view_size[0]/2
        self.circle = self.scene().addEllipse(QtCore.QRectF(0, 0, diameter, diameter),
                                              QtGui.QPen(Colors().red,3),
                                              QtGui.QBrush(QtGui.QColorConstants.Transparent))
        self.circle.setPos(self.sample_size[0]/2 - diameter/2, self.sample_size[1]/2 - diameter/2)
        self.circle.setZValue(-99)
        self.now_rect = self.scene().addRect(QtCore.QRectF(0, 0,
                                                           self.fov_size[0], self.fov_size[1]),
                                             QtGui.QPen(Colors().blue,1),
                                             QtGui.QBrush(QtGui.QColorConstants.Transparent))
        self.now_rect.setZValue(100)
        self.now_rect.setPos(pos[0], pos[1])
        self.arrow = self.scene().addPolygon(self.oof_arrow(),
                                QtGui.QPen(QtGui.QColorConstants.Transparent),
                                QtGui.QBrush(Colors().blue))
        self.arrow.setPos(100,100)
        self.arrow.setVisible(0)
        self.rect = QtCore.QRectF(pos[0], pos[1],
                                 self.fov_size[0], self.fov_size[1])

        self.laser = True
        self.stage_offset = [0, 0]
        self.zoom_factors = (0.8, 1.25)
        self.scale(5, 5)

        # Enable Zoom
        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self._zoom = 0
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)

        # Connect to mmc signals
        self.mmc.events.XYStagePositionChanged.connect(self.stage_moved)
        # self.mmc.events.imageSnapped.connect(self.increase_values)
        self.mmc.mda.events.frameReady.connect(self.frame_ready)
        self.mmc.events.liveFrameReady.connect(self.frame_ready)
        self.increase_values_signal.connect(self.increase_values)


    def frame_ready(self, frame, event, metadata):
        self.increase_values_signal.emit(frame, event, metadata)

    def stage_moved(self, name, new_pos0, new_pos1):
        print("STAGE MOVED IN HISTORY", new_pos0, new_pos1)
        new_pos = [new_pos0, new_pos1]
        self.stage_pos = new_pos
        new_pos = [x/10 for x in new_pos]
        offset = [x/10 for x in self.stage_offset]
        pos = self.rectangle_pos(list(map(operator.sub, new_pos, offset)))
        self.rect = QtCore.QRectF(pos[0], pos[1], self.fov_size[0], self.fov_size[1])
        self.my_pixmap.setPixmap(QtGui.QPixmap.fromImage(self.map))
        self.now_rect.setPos(QtCore.QPointF(pos[0], pos[1]))
        self.set_oof_arrow()
        self.repaint()
        self.xy_stage_position_python.emit(self.stage_pos)

    def rectangle_pos(self, pos):
        rect_pos = [int(self.sample_size[0]*0.5 + pos[0] - self.fov_size[0]/2),
                    int(self.sample_size[1]*0.5 + pos[1] - self.fov_size[1]/2)]
        return rect_pos

    def set_oof_arrow(self):
        pos = self.rectangle_pos(list(map(operator.sub, self.stage_pos, self.stage_offset)))
        y = self.check_limits(pos[1]+self.fov_size[1]/2)
        x = self.check_limits(pos[0]+self.fov_size[0]/2)
        self.arrow.setVisible(1)
        offset = 25
        if x == offset and y == offset:
            self.arrow.setPos(QtCore.QPointF(offset, offset))
            self.arrow.setRotation(-45)
        elif x == offset and y == self.sample_size[0]-offset:
            self.arrow.setPos(QtCore.QPointF(offset, self.sample_size[1]-offset))
            self.arrow.setRotation(-135)
        elif x == self.sample_size[0]-offset and y == self.sample_size[0]-offset:
            self.arrow.setPos(QtCore.QPointF(self.sample_size[0]-offset, self.sample_size[1]-offset))
            self.arrow.setRotation(135)
        elif x == self.sample_size[0]-offset and y == offset:
            self.arrow.setPos(QtCore.QPointF(self.sample_size[0]-offset, offset))
            self.arrow.setRotation(45)
        elif pos[0] - self.sample_size[0]/2 > self.sample_size[0]/2:
            self.arrow.setPos(QtCore.QPointF(self.sample_size[0]-offset, y))
            self.arrow.setRotation(90)
        elif pos[0] - self.sample_size[0]/2  < -self.sample_size[0]/2:
            self.arrow.setRotation(-90)
            self.arrow.setPos(QtCore.QPointF(offset, y))
        elif pos[1] - self.sample_size[1]/2 < -self.sample_size[1]/2:
            self.arrow.setRotation(0)
            self.arrow.setPos(QtCore.QPointF(x, offset))
        elif pos[1] - self.sample_size[1]/2  > self.sample_size[1]/2:
            self.arrow.setRotation(180)
            self.arrow.setPos(QtCore.QPointF(x, self.sample_size[1]-offset))
        else:
            self.arrow.setVisible(0)

    def check_limits(self, pos):
        if pos < 0:
            pos = 25
        elif pos > self.sample_size[0]:
            pos = self.sample_size[0]-25
        return pos

    def oof_arrow(self):
        arrow = QtGui.QPolygonF()
        arrow.append(QtCore.QPointF(-20, 0))
        arrow.append(QtCore.QPointF(0,-20))
        arrow.append(QtCore.QPointF(20, 0))
        arrow.append(QtCore.QPointF(-20, 0))
        return arrow

    def increase_values(self, img, event= None, metadata=None):
        self.painter = self.define_painter()
        current_color = self.map.pixelColor(self.rect.center().toPoint()).getHsv()

        #make the image smaller
        scale = int(np.ceil(img.shape[0]/self.fov_size[0]))
        img = img[::scale, ::scale]
        img = np.require(img/img.max()*255, np.uint8, 'C')
        width, height = img.shape

        t0 = time.perf_counter()
        # Take the current color and cycle along the hue rom green to red over several frames
        if abs(sum([x - y for x,y in zip(current_color, (0, 0, 0, 255))])) < 10:

            my_color = [162, 30, 230/255, 15]
        else:
            slope = 10
            my_color = [max([0, current_color[0] - slope]),
                      min([181, current_color[1] + slope*5]),
                      230/255,
                      max(25, int(255-current_color[0]*1.4))]

        color = QtGui.QColor(0, 0, 0, 255)
        self.painter.setBrush(QtGui.QBrush(color))
        self.painter.drawRect(self.rect)
        # print(current_color)
        # print(my_color)
        qimage = QtGui.QImage(img.data, width, height, height, QtGui.QImage.Format_Grayscale8)
        qimage = qimage.convertToFormat(QtGui.QImage.Format_Indexed8)
        color_table = [QtGui.QColor().fromHsv(my_color[0], my_color[1], int(i*my_color[2]),
                                              my_color[3]).rgba()
                              for i in range(256)]
        qimage.setColorTable(color_table)
        self.painter.drawImage(self.rect.topLeft(), qimage)

        # my_color = QtGui.QColor().fromHsv(*my_color)
        # self.painter.setBrush(QtGui.QBrush(my_color))
        # self.painter.setCompositionMode(QtGui.QPainter.CompositionMode_Multiply)
        # self.painter.drawRect(self.rect)

        self.my_pixmap.setPixmap(QtGui.QPixmap.fromImage(self.map))
        # print("time for drawing: ", time.perf_counter() - t0)
        self.painter.end()

    def define_painter(self, alpha=100):
        painter = QtGui.QPainter(self.map)
        painter.setPen(QtGui.QPen(QtGui.QColorConstants.Transparent))
        return painter

    def keyPressEvent(self, event):
        # print("KEY pressed: ", event.key())
        # print(event.modifiers() & QtCore.Qt.ShiftModifier)
        if event.modifiers() & QtCore.Qt.ShiftModifier:
            move_modifier = 0.2 * self.size_adjust
        else:
            move_modifier = 1 * self.size_adjust
        if event.key() == 16777236:
            event.accept()
            self.stage_pos[0] = self.stage_pos[0] - self.fov_size[0] * move_modifier
            self.stage_moved('default', self.stage_pos[0], self.stage_pos[1])
        if event.key() == 16777234:
            event.accept()
            self.stage_pos[0] = self.stage_pos[0] + self.fov_size[0] * move_modifier
            self.stage_moved('default', self.stage_pos[0], self.stage_pos[1])
        if event.key() == 16777235:
            event.accept()
            self.stage_pos[1] = self.stage_pos[1] + self.fov_size[1] * move_modifier
            self.stage_moved('default', self.stage_pos[0], self.stage_pos[1])
        if event.key() == 16777237:
            event.accept()
            self.stage_pos[1] = self.stage_pos[1] - self.fov_size[1] * move_modifier
            self.stage_moved('default', self.stage_pos[0], self.stage_pos[1])
        if event.key() == 16777220:
            "Enter: Reset drawn positions"
            self.clear_history()
        if event.key() == 16777221:
            "NumPadEnter: reset position of rectangle"
            self.clear_history()
            self.stage_offset = copy.deepcopy(self.stage_pos)
            self.stage_moved(self.stage_pos)

    def clear_history(self):
            self.map = QtGui.QImage(self.sample_size[0], self.sample_size[1],
                                    QtGui.QImage.Format.Format_Grayscale8)
            self.my_pixmap.setPixmap(QtGui.QPixmap.fromImage(self.map))

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            factor = 0.8
            self._zoom -= 1
        else:
            factor = 1.25
            self._zoom += 1
        if self._zoom > 0:
            self.scale(factor, factor)
        elif self._zoom == 0:
            self.fitInView()
        else:
            self._zoom = 0

    def fitInView(self, scale=False):
        rect = QtCore.QRectF(self.my_pixmap.pixmap().rect())
        # if not rect.isNull():
        self.setSceneRect(rect)
        unity = self.transform().mapRect(QtCore.QRectF(0, 0, 1, 1))
        self.scale(1 / unity.width(), 1 / unity.height())
        viewrect = self.viewport().rect()
        scenerect = self.transform().mapRect(rect)
        factor = min(viewrect.width() / scenerect.width(),
                        viewrect.height() / scenerect.height())
        self.scale(factor, factor)
        self._zoom = 0

    def resizeEvent(self, event):
        self.centerOn(self.now_rect)

if __name__ == "__main__":
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtWidgets import QApplication
    import useq, time
    from qtpy.QtCore import QTimer

    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()

    mmc.setProperty("Camera", "Mode", "Noise")
    mmc.setProperty("Camera", "StripeWidth", 2)
    mmc.setProperty("Camera", "OnCameraCCDXSize", 2048)
    mmc.setProperty("Camera", "OnCameraCCDYSize", 2048)

    app = QApplication([])

    from pymmcore_widgets import StageWidget, LiveButton
    stage = StageWidget("XY", mmcore=mmc)
    stage.show()

    # live = LiveButton(mmcore=mmc)
    # live.show()

    from isim_control.gui.position_history import PositionHistory
    history = PositionHistory(mmc)
    history.show()

    # timers = []
    # for i in range(11):
    #     timer = QTimer()
    #     timer.setSingleShot(True)
    #     mode = "Noise" if i % 2 == 0 else "Artificial Waves"
    #     timer.timeout.connect(lambda mode=mode: mmc.setProperty("Camera", "Mode", mode))
    #     # timer.timeout.connect(lambda mode=mode: print(mode))
    #     timer.start(5000 * i)
    #     timers.append(timer)

    time.sleep(1)
    seq = useq.MDASequence(time_plan={"interval": 0.5, "loops": 100})
    mmc.run_mda(seq)

    app.exec_()

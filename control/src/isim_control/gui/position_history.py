from pymmcore_plus import CMMCorePlus
from useq import MDAEvent
import operator, time
import numpy as np
import copy
from qtpy import QtCore, QtGui, QtWidgets

from isim_control.pubsub import Broker, Subscriber
from isim_control.io.remote_datastore import RemoteDatastore
from isim_control.io.keyboard import KeyboardListener


def position_history_process(event_queue, name: str):
    app = QApplication([])
    broker = Broker(pub_queue=event_queue, auto_start=False)
    remote_datastore = RemoteDatastore(name)
    history = PositionHistory(key_listener=KeyboardListener(),
                              datastore=remote_datastore)
    history.sub = Subscriber(["datastore, sequence"], {"new_frame": [history.frame_ready],
                              "xy_stage_position_changed": [history.stage_moved],})
    broker.attach(history)
    history.show()
    app.exec_()


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

    def __init__(self, mmcore: CMMCorePlus|None = None, key_listener: QtCore.QObject | None = None,
                 datastore: RemoteDatastore|None =  None, parent:QtWidgets.QWidget=None):
        super().__init__()
        self.max_img = 0
        self.datastore = datastore

        # Set the properties for the window so that everything is shown and we don't have Scrollbars
        self.view_size = (3000, 3000)
        self.setScene(QtWidgets.QGraphicsScene(self))
        self.setBaseSize(self.view_size[0], self.view_size[1])
        self.setSceneRect(0, 25, self.view_size[0], self.view_size[1] - 50)
        self.scale(1, -1)
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
        if mmcore:
            self.mmc = mmcore
            self.mmc.events.XYStagePositionChanged.connect(self.stage_moved)
            # self.mmc.events.imageSnapped.connect(self.increase_values)
            self.mmc.mda.events.frameReady.connect(self.frame_ready)
            self.mmc.events.liveFrameReady.connect(self.frame_ready)
        self.increase_values_signal.connect(self.increase_values)

        if key_listener:
            self.key_listener = key_listener
            self.installEventFilter(self.key_listener)

    def frame_ready(self, frame, event, metadata):
        self.increase_values_signal.emit(frame, event, metadata)

    def frame_ready_datastore(self, event, shape, idx, meta):
        frame = self.datastore.get_frame(idx, shape[0], shape[1])
        self.increase_values_signal.emit(frame, MDAEvent(**event), meta)

    def stage_moved(self, name, new_pos0, new_pos1):
        # print("STAGE MOVED IN HISTORY", new_pos0, new_pos1)
        new_pos = [new_pos0, new_pos1]
        self.stage_pos = new_pos
        new_pos = [x/10 for x in new_pos]
        offset = [x/10 for x in self.stage_offset]
        pos = self.rectangle_pos(list(map(operator.sub, new_pos, offset)))
        self.rect = QtCore.QRectF(pos[0], pos[1], self.fov_size[0], self.fov_size[1])
        self.my_pixmap.setPixmap(QtGui.QPixmap.fromImage(self.map))
        self.now_rect.setPos(QtCore.QPointF(pos[0], pos[1]))
        self.repaint()
        # self.xy_stage_position_python.emit(self.stage_pos)

    def rectangle_pos(self, pos):
        rect_pos = [int(self.sample_size[0]*0.5 + pos[0] - self.fov_size[0]/2),
                    int(self.sample_size[1]*0.5 + pos[1] - self.fov_size[1]/2)]
        return rect_pos

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
        current_img = self.map.copy(self.rect.toRect())
        width, height = current_img.width(), current_img.height()
        ptr = current_img.bits()
        ptr.setsize(height*width*4)
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
        sum_arr = np.sum(arr, 2)
        max_value_px = np.where(sum_arr == sum_arr.max())
        current_color = arr[max_value_px[0], max_value_px[1]][0]
        current_color = QtGui.QColor(current_color[2], current_color[1], current_color[0]).getHsv()

        #make the image smaller
        scale = int(np.ceil(img.shape[0]/self.fov_size[0]))
        img = img[::scale, ::scale]
        if event == "led":
            img = img.max() - img
            paint_max = img.max()
        else:
            self.max_img = max(self.max_img, img.max())
            paint_max = self.max_img
            if paint_max > img.max()*3:
                paint_max = img.max()*3

            img = img - img.min()
        img = np.require(img/paint_max*255, np.uint8, 'C')
        img = np.flipud(np.rot90(img)).copy()
        width, height = img.shape

        t0 = time.perf_counter()
        # Take the current color and cycle along the hue from green to red over several frames
        if abs(sum(x-y for x,y in zip(current_color, (0, 0, 0, 255)))) < 10:
            my_color = [162, 30, 1, 255]
        else:
            slope = 8
            my_color = [max([0, current_color[0] - slope]),
                      min([255, current_color[1] + slope*5]),
                      1, #230/255,
                      min(255, max(80, int(255-current_color[0])))]
        color = QtGui.QColor(0, 0, 0, 255)
        self.painter.setBrush(QtGui.QBrush(color))
        self.painter.drawRect(self.rect)

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
        if event.key() == 16777220:
            "Enter: Reset drawn positions"
            self.clear_history()
        if event.key() == 16777221:
            "NumPadEnter: reset position of rectangle"
            self.clear_history()
            self.stage_offset = copy.deepcopy(self.stage_pos)
            self.stage_moved("XY", self.stage_pos[0], self.stage_pos[1])

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

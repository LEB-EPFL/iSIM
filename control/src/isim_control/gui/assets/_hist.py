
from PyQt6 import QtGui
from qtpy.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout
from qtpy.QtCore import Qt, QPointF, QObject, Signal
from qtpy.QtGui import QPainter, QBrush, QPixmap
import numpy as np
from pymmcore_plus import CMMCorePlus


class HistPlot(QLabel):
    update_data_event = Signal(np.ndarray)
    def __init__(self, mmcore: CMMCorePlus|None = None, parent: QWidget|None = None):
        super().__init__(parent)
        self.mmcore = mmcore

        self.hist = np.zeros(100)
        self.pixmap = QPixmap(self.size())
        self.max_x = 2**16
        self.hist_calculator = self.HistCalculator()
        self.update_data_event.connect(self.hist_calculator.calc_hist)
        self.hist_calculator.complete.connect(self.new_data)

        self.setMaximumHeight(100)
        if self.mmcore:
            self.mmcore.events.liveFrameReady.connect(self.hist_calculator.calc_hist)

    def update_data(self, img: np.ndarray) -> None:
        self.update_data_event.emit(img)

    class HistCalculator(QObject):
        complete = Signal(np.ndarray)
        def calc_hist(self, img: np.ndarray, *_):
            hist = np.bincount(img.ravel(), minlength=2**16)
            hist = hist[::100]
            hist = np.log10(hist, out=np.zeros_like(hist, dtype=np.float64), where=(hist!=0))
            self.complete.emit(hist)

    def new_data(self, hist: np.ndarray):
        self.hist = hist
        self.update()

    def paintEvent(self, a0: QtGui.QPaintEvent | None) -> None:
        self.pixmap.fill(Qt.black)
        self.painter = QPainter(self.pixmap)
        self.painter.setPen(Qt.gray)
        self.painter.setBrush(QBrush(Qt.red, Qt.NoBrush))
        path = QtGui.QPainterPath()
        path.moveTo(QPointF(0, self.size().height()*0.9))

        hist = self.hist/np.max(self.hist)*self.size().height()*0.8
        hist = - hist + self.size().height()*0.9

        width = self.size().width()
        bins = np.linspace(0, width*2**16/self.max_x, len(hist))
        for  i, (x, y) in enumerate(zip(bins, hist)):
            if x < width:
                path.lineTo(x, y)
            else:
                label_pos = width*0.9
                self.painter.drawText(QPointF(label_pos, 10), str(int(0.9*self.max_x)))
                break

        self.painter.drawPath(path)
        self.painter.end()
        painter = QtGui.QPainter(self)
        painter.drawPixmap(0, 0, self.pixmap)
        return super().paintEvent(a0)

    def resizeEvent(self, a0: QtGui.QResizeEvent | None) -> None:
        self.pixmap = QPixmap(self.size())
        super().resizeEvent(a0)

    def set_max(self, max_x: int):
        self.max_x = max_x


if __name__ == "__main__":
    class Histogram(QWidget):
        def __init__(self, parent: QWidget|None = None):
            super().__init__(parent)
            self.img = np.random.normal(3000, 500, (2048, 2048)).astype(np.uint16)

            self.plot = HistPlot()

            self.update = QPushButton("Update")
            self.update.clicked.connect(self._update)
            self.bins = np.arange(0, 2**16, 100).astype(np.uint16)
            self.hist2 = np.zeros(len(self.bins))

            self.setLayout(QVBoxLayout())
            self.layout().addWidget(self.plot)
            self.layout().addWidget(self.update)

        def _update(self):
            self.plot.update_data()
    from qtpy.QtWidgets import QApplication
    app = QApplication([])
    hist = Histogram()
    hist.show()
    app.exec_()

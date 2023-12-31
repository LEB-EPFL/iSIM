from zlib import DEF_BUF_SIZE
from pycromanager import Core, Studio
from PyQt5.QtCore import QObject, QTimer, pyqtSlot
from PyQt5.QtGui import QImage

import numpy
import time
from qimage2ndarray import gray2qimage


class MicroManagerControl(QObject):

    def __init__(self, event_thread=None):
        super().__init__()
        if event_thread is None:
            self.core = Core()
            self.studio = Studio()
        else:
            self.event_thread = event_thread
            self.studio = Studio()
            self.core = Core()
            # self.studio = event_thread.studio
            # self.core = event_thread.core
        self.data = self.studio.data
        self.live = self.studio.get_snap_live_manager()
        self.image_format = QImage.Format.Format_Grayscale16
        self.LUT = []
        self.zPosition = self.core.get_position()
        self.move_to = self.zPosition

    @pyqtSlot(object)
    def set_xy_position(self, pos: tuple):
        self.core.set_xy_position(pos[0], pos[1])

    @pyqtSlot(float)
    def track_z_change(self, pos: float):
        print(pos)
        if self.move_to == self.zPosition:
            self.set_z_position(self.zPosition + pos)
        new_pos = self.move_to + pos
        if new_pos < 200 and new_pos > 0:
            self.move_to = self.move_to + pos

    @pyqtSlot(float)
    def set_z_position(self, pos: float):
        self.event_thread.blockZ = True
        print("set stage to ", pos)
        pos = pos if pos > 0 else 0
        pos = pos if pos < 202 else 202
        self.core.set_position(pos)

    @pyqtSlot()
    def stop_live(self):
        self.live.set_live_mode_on(False)

    def set_bit_depth(self):
        bit_depth = self.core.get_image_bit_depth
        if bit_depth == 8:
            self.image_format = QImage.Format.Format_Grayscale8
        elif bit_depth == 16:
            self.image_format = QImage.Format.Format_Grayscale16

    @pyqtSlot(object)
    def convert_image(self, image: numpy.ndarray, normalize: bool = True):
        # t1 = time.perf_counter()
        qimage = gray2qimage(image, normalize=normalize)
        # print(time.perf_counter() - t1)
        return qimage

    def close(self):
        pass
        # self.bridge.close()


if __name__ == '__main__':
    import gui.MainGUI as MainGUI
    MainGUI.main()

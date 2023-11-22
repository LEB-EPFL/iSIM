from pymmcore_widgets import ImagePreview

from qtpy.QtWidgets import QWidget, QGridLayout, QPushButton, QFileDialog
from superqt import fonticon
from fonticon_mdi6 import MDI6
from tifffile import imsave
from pathlib import Path

from isim_control.settings_translate import load_settings, save_settings


class iSIMPreview(QWidget):
    def __init__(self, mmcore):
        super().__init__()
        self._mmc = mmcore
        self.preview = ImagePreview(mmcore=mmcore)
        self.current_frame = None
        self.save_loc = load_settings("live_save_location").get("path", Path.home())

        self._mmc.events.liveFrameReady.connect(self.preview._on_image_snapped)
        self._mmc.events.liveFrameReady.connect(self.new_frame)

        self.setWindowTitle("Preview")
        self.setLayout(QGridLayout())
        self.layout().addWidget(self.preview, 0, 0, 1, 5)

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_image)

        self.collapse_btn = QPushButton()
        self.collapse_btn.setIcon(fonticon.icon(MDI6.arrow_collapse_all))
        self.collapse_btn.clicked.connect(self.collapse_view)

        self.layout().addWidget(self.save_btn, 1, 0)
        self.layout().addWidget(self.collapse_btn, 1, 4)

    def new_frame(self, image, event, meta):
        self.current_frame = image

    def save_image(self):
        if self.current_frame is not None:
            self.save_loc, _ = QFileDialog.getSaveFileName(directory=self.save_loc)
            print(self.save_loc)
            try:
                imsave(self.save_loc[0], self.current_frame)
            except Exception as e:
                import traceback
                print(traceback.format_exc())

    def collapse_view(self):
        self.preview.view.camera.set_range()

    def closeEvent(self, event):
        save_settings({"path": str(self.save_loc)}, "live_save_location")
        super().closeEvent(event)
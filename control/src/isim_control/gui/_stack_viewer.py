from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Mapping

import numpy as np
from fonticon_mdi6 import MDI6
from qtpy import QtCore, QtWidgets
from qtpy.QtCore import QTimer, Signal
from superqt import fonticon
from superqt.cmap._cmap_utils import try_cast_colormap
from useq import MDAEvent, MDASequence

from isim_control.gui.assets._channel_row import ChannelRow
from isim_control.gui.assets._labeled_slider import LabeledVisibilitySlider
from isim_control.gui.assets.save_button import SaveButton

from isim_control.io.datastore import QOMEZarrDatastore

DIMENSIONS = ["t", "z", "c", "p", "g"]
AUTOCLIM_RATE = 1  # Hz   0 = inf

try:
    from vispy import scene, visuals
except ImportError as e:
    raise ImportError(
        "vispy is required for StackViewer. "
        "Please run `pip install pymmcore-widgets[image]`"
    ) from e

if TYPE_CHECKING:
    import cmap
    from pymmcore_plus import CMMCorePlus
    from qtpy.QtCore import QCloseEvent
    from qtpy.QtWidgets import QWidget
    from vispy.scene.events import SceneMouseEvent


class StackViewer(QtWidgets.QWidget):
    """A viewer for MDA acquisitions started by MDASequence in pymmcore-plus events.

    Parameters
    ----------
    transform: (int, bool, bool) rotation mirror_x mirror_y.
    """

    _slider_settings = Signal(dict)
    _new_channel = Signal(int, str)

    def __init__(
        self,
        datastore: QOMEZarrDatastore | None = None,
        sequence: MDASequence | None = None,
        mmcore: CMMCorePlus | None = None,
        parent: QWidget | None = None,
        size: tuple[int, int] | None = None,
        transform: tuple[int, bool, bool] = (0, True, False),
        save_button: bool = True,
    ):
        super().__init__(parent=parent)
        self._reload_position()
        self.sequence = sequence
        self.canvas_size = size
        self.transform = transform
        self._mmc = mmcore
        self._clim = "auto"
        self.cmaps = [try_cast_colormap(x) for x in self.cmap_names]
        self.display_index = {dim: 0 for dim in DIMENSIONS}

        self.main_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.construct_canvas()
        self.main_layout.addWidget(self._canvas.native)

        self.info_bar = QtWidgets.QLabel()
        self.info_bar.setSizePolicy(
            QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed
        )
        self.main_layout.addWidget(self.info_bar)

        self._create_sliders(sequence)

        self.datastore = datastore or QOMEZarrDatastore()
        self.datastore.frame_ready.connect(self.frameReady)
        if not datastore:
            if self._mmc:
                self._mmc.mda.events.frameReady.connect(self.datastore.frameReady)
                self._mmc.mda.events.sequenceFinished.connect(
                    self.datastore.sequenceFinished
                )
                self._mmc.mda.events.sequenceStarted.connect(
                    self.datastore.sequenceStarted
                )
            else:
                import warnings

                warnings.warn(
                    "No datastore or mmcore provided, connect manually.",
                    stacklevel=2,
                )

        if self._mmc:
            # Otherwise connect via listeners_connected or manually
            self._mmc.mda.events.sequenceStarted.connect(self.sequenceStarted)

        self._new_channel.connect(self.channel_row.box_visibility)

        self.images: list[scene.visuals.Image] = []
        self.frame = 0
        self.ready = False
        self.current_channel = 0
        self.pixel_size = 1.0

        self.clim_timer = QtCore.QTimer()
        self.clim_timer.setInterval(int(1000 // AUTOCLIM_RATE))
        self.clim_timer.timeout.connect(self.on_clim_timer)

        self.destroyed.connect(self._disconnect)

        self.collapse_btn = QtWidgets.QPushButton()
        self.collapse_btn.setIcon(fonticon.icon(MDI6.arrow_collapse_all))
        self.collapse_btn.clicked.connect(self._collapse_view)

        self.bottom_buttons = QtWidgets.QHBoxLayout()
        self.bottom_buttons.addWidget(self.collapse_btn)
        if save_button:
            self.save_btn = SaveButton(self.datastore)
            self.bottom_buttons.addWidget(self.save_btn)
        self.main_layout.addLayout(self.bottom_buttons)

        if sequence:
            self.sequenceStarted(sequence)

    def construct_canvas(self) -> None:
        if self.canvas_size:
            self.img_size = self.canvas_size
        elif self._mmc:
            self.img_size = (self._mmc.getImageHeight(), self._mmc.getImageWidth())
        else:
            self.img_size = (512, 512)
        self._canvas = scene.SceneCanvas(
            size=self.img_size, parent=self, keys="interactive"
        )
        self._canvas._send_hover_events = True
        self._canvas.events.mouse_move.connect(self.on_mouse_move)
        self.view = self._canvas.central_widget.add_view()
        self.view.camera = scene.PanZoomCamera(aspect=1)
        self.view.camera.flip = (self.transform[1], self.transform[2], False)
        self.view.camera.set_range(
            (0, self.img_size[0]), (0, self.img_size[1]), margin=0
        )
        rect = self.view.camera.rect
        self.view_rect = (rect.pos, rect.size)
        self.view.camera.aspect = 1

    def sequenceStarted(self, sequence: MDASequence) -> None:
        """Sequence started by the mmcore. Adjust our settings, make layers etc."""
        self.ready = False
        self.sequence = sequence
        self.pixel_size = self._mmc.getPixelSizeUm() if self._mmc else self.pixel_size
        print("PIXEL_SIZE", self.pixel_size)
        # Sliders
        for dim in DIMENSIONS[:3]:
            if sequence.sizes.get(dim, 1) > 1:
                self._slider_settings.emit(
                    {"index": dim, "show": True, "max": sequence.sizes[dim] - 1}
                )
            else:
                self._slider_settings.emit({"index": dim, "show": False, "max": 1})
        # Channels
        nc = max(sequence.sizes.get("c", 1), 1)
        self.ng = max(sequence.sizes.get("g", 1), 1)
        self.images = []

        for c in range(nc):
            self.images.append([])
            for g in range(self.ng):
                image = scene.visuals.Image(
                    np.zeros(self._canvas.size).astype(np.uint16),
                    parent=self.view.scene,
                    cmap=self.cmaps[c].to_vispy(),
                    clim=(0, 1),
                )
                trans = visuals.transforms.linear.MatrixTransform()
                trans.rotate(self.transform[0], (0, 0, 1))
                image.transform = self._get_image_position(trans, sequence, g)
                image.interactive = True
                if c > 0:
                    image.set_gl_state("additive", depth_test=False)
                else:
                    image.set_gl_state(depth_test=False)
                self.images[c].append(image)
            self.current_channel = c
            try:
                self._new_channel.emit(c, sequence.channels[c].config)
            except IndexError:
                self._new_channel.emit(c, "Default")
        self._collapse_view()
        self.ready = True

    def _handle_channel_clim(
        self, values: tuple[int, int], channel: int, set_autoscale: bool = True
    ) -> None:
        for g in range(self.ng):
            self.images[channel][g].clim = values
        if self.channel_row.boxes[channel].autoscale_chbx.isChecked() and set_autoscale:
            self.channel_row.boxes[channel].autoscale_chbx.setCheckState(
                QtCore.Qt.Unchecked
            )
        self._canvas.update()

    def _handle_channel_cmap(self, colormap: cmap.Colormap, channel: int) -> None:
        for g in range(self.ng):
            self.images[channel][g].cmap = colormap.to_vispy()
        if colormap.name not in self.cmap_names:
            self.cmap_names.append(self.cmap_names[channel])
        self.cmap_names[channel] = colormap.name
        self._canvas.update()

    def _handle_channel_visibility(self, state: bool, channel: int) -> None:
        for g in range(self.ng):
            self.images[channel][g].visible = self.channel_row.boxes[
                channel
            ].show_channel.isChecked()
        if self.current_channel == channel:
            channel_to_set = channel - 1 if channel > 0 else channel + 1
            channel_to_set = 0 if len(self.channel_row.boxes) == 1 else channel_to_set
            self.channel_row._handle_channel_choice(
                self.channel_row.boxes[channel_to_set].channel
            )
        self._canvas.update()

    def _handle_channel_autoscale(self, state: bool, channel: int) -> None:
        slider = self.channel_row.boxes[channel].slider
        if state == 0:
            self._handle_channel_clim(slider.value(), channel, set_autoscale=False)
        else:
            clim = (
                slider.minimum(),
                slider.maximum(),
            )
            self._handle_channel_clim(clim, channel, set_autoscale=False)

    def _handle_channel_choice(self, channel: int) -> None:
        print("Setting current channel", channel)
        self.current_channel = channel

    def _create_sliders(self, sequence: MDASequence | None = None) -> None:
        n_channels = 5 if sequence is None else sequence.sizes.get("c", 1)
        self.channel_row: ChannelRow = ChannelRow(n_channels)
        self.channel_row.visible.connect(self._handle_channel_visibility)
        self.channel_row.autoscale.connect(self._handle_channel_autoscale)
        self.channel_row.new_clims.connect(self._handle_channel_clim)
        self.channel_row.new_cmap.connect(self._handle_channel_cmap)
        self.channel_row.selected.connect(self._handle_channel_choice)
        self.layout().addWidget(self.channel_row)

        if sequence is not None:
            dims = [x for x in sequence.sizes.keys() if sequence.sizes[x] > 0]
        else:
            dims = DIMENSIONS
        if "c" in dims:
            dims.remove("c")
        self.sliders: list[LabeledVisibilitySlider] = []
        for dim in dims:
            slider = LabeledVisibilitySlider(dim, orientation=QtCore.Qt.Horizontal)
            # TODO: this should trigger a timer instead of directly calling the function
            slider.sliderMoved.connect(self.on_display_timer)
            self._slider_settings.connect(slider._visibility)
            self.layout().addWidget(slider)
            slider.hide()
            self.sliders.append(slider)
        # print("Number of sliders constructed: ", len(self.sliders))

    def on_mouse_move(self, event: SceneMouseEvent) -> None:
        """Mouse moved on the canvas, display the pixel value and position."""
        # https://groups.google.com/g/vispy/c/sUNKoDL1Gc0/m/E5AG7lgPFQAJ
        self.view.interactive = False
        images = []
        # Get the images the mouse is over
        while image := self._canvas.visual_at(event.pos):
            images.append(image)
            image.interactive = False
        for image in images:
            image.interactive = True
        self.view.interactive = True
        if images == []:
            transform = self.view.get_transform("canvas", "visual")
            p = [int(x) for x in transform.map(event.pos)]
            info = f"[{p[0]}, {p[1]}]"
            self.info_bar.setText(info)
            return
        # Adjust channel index is channel(s) are not visible
        real_channel = self.current_channel
        for i in range(self.current_channel):
            i_visible = self.channel_row.boxes[i].show_channel.isChecked()
            real_channel = real_channel - 1 if not i_visible else real_channel
        images.reverse()
        transform = images[real_channel].get_transform("canvas", "visual")
        p = [int(x) for x in transform.map(event.pos)]
        try:
            pos = f"[{p[0]}, {p[1]}]"
            value = f"{images[real_channel]._data[p[1], p[0]]}"
            info = f"{pos}: {value}"
            self.info_bar.setText(info)
        except IndexError:
            info = f"[{p[0]}, {p[1]}]"
            self.info_bar.setText(info)

    def on_display_timer(self) -> None:
        """Update display, usually triggered by QTimer started by slider click."""
        old_index = self.display_index.copy()
        for slider in self.sliders:
            self.display_index[slider.name] = slider.value()
        if old_index == self.display_index:
            return
        if (sequence := self.sequence) is None:
            return
        for g in range(self.ng):
            for c in range(sequence.sizes.get("c", 1)):
                frame = self.datastore.get_frame(
                    MDAEvent(
                        index={
                            "t": self.display_index["t"],
                            "z": self.display_index["z"],
                            "c": c,
                            "g": g,
                            "p": 0,
                        }
                    )
                )
                self.display_image(frame, c, g)
        self._canvas.update()

    def frameReady(self, event: MDAEvent) -> None:
        """Frame received from acquisition, display the image, update sliders etc."""
        if not self.ready:
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.frameReady(event))
            timer.start(100)
            return
        indices = self.complement_indices(event.index)
        img = self.datastore.get_frame(event)
        # Update display
        display_indices = self._set_sliders(indices)
        if display_indices == indices:
            self.display_image(img, indices.get("c", 0), indices.get("g", 0))
            # Handle Autoscaling
            clim_slider = self.channel_row.boxes[indices.get("c", 0)].slider
            clim_slider.setRange(
                min(clim_slider.minimum(), img.min()),
                max(clim_slider.maximum(), img.max()),
            )
            if self.channel_row.boxes[indices.get("c", 0)].autoscale_chbx.isChecked():
                clim_slider.setValue(
                    [
                        min(clim_slider.minimum(), img.min()),
                        max(clim_slider.maximum(), img.max()),
                    ]
                )
            self.on_clim_timer(indices.get("c", 0))

    def _set_sliders(self, indices: dict) -> dict:
        """New indices from outside the sliders, update."""
        display_indices = copy.deepcopy(indices)
        for slider in self.sliders:
            if slider.lock_btn.isChecked():
                display_indices[slider.name] = slider.value()
                continue
            # This blocking doesn't seem to work
            # blocked = slider.blockSignals(True)
            slider.setValue(display_indices[slider.name])
            # slider.setValue(indices[slider.name])
            # slider.blockSignals(blocked)
        return display_indices

    def display_image(self, img: np.ndarray, channel: int = 0, grid: int = 0) -> None:
        self.images[channel][grid].set_data(img)
        # Should we do this? Might it slow down acquisition while in the same thread?
        self._canvas.update()

    def on_clim_timer(self, channel: int | None = None) -> None:
        channel_list = (
            list(range(len(self.channel_row.boxes))) if channel is None else [channel]
        )
        for grid in range(self.ng):
            for channel in channel_list:
                if (
                    self.channel_row.boxes[channel].autoscale_chbx.isChecked()
                    and self.images[channel][grid].visible
                ):
                    # TODO: percentile here, could be in gui
                    clim = np.percentile(self.images[channel][grid]._data, [0, 100])
                    self.images[channel][grid].clim = clim
        self._canvas.update()

    def _get_image_position(
        self,
        trans: visuals.transforms.linear.MatrixTransform,
        sequence: MDASequence,
        g: int,
    ) -> visuals.transforms.linear.MatrixTransform:
        translate = [round(x) for x in ((1, 1) - trans.matrix[:2, :2].dot((1, 1))) / 2]
        if sequence.grid_plan:
            sub_seq = MDASequence(grid_plan=sequence.grid_plan)
            sub_event = list(sub_seq.iter_events())[g]
            x_pos = sub_event.x_pos or 0
            y_pos = sub_event.y_pos or 0
            trans.translate(
                (
                    (translate[1] - 1) * self.img_size[0],
                    translate[0] * self.img_size[1],
                    0,
                )
            )
            trans.translate(
                (
                    -x_pos / self.pixel_size,
                    y_pos / self.pixel_size,
                    0,
                )
            )
            self._expand_canvas_view(sub_event)
        else:
            trans.translate(
                (
                    (1 - translate[1]) * self.img_size[0],
                    translate[0] * self.img_size[1],
                    0,
                )
            )
            self.view_rect = (
                (0 - self.img_size[0] / 2, 0 - self.img_size[1] / 2),
                (self.img_size[0], self.img_size[1]),
            )
        return trans

    def _expand_canvas_view(self, event: MDAEvent) -> None:
        """Expand the canvas view to include the new image."""
        x_pos = event.x_pos or 0
        y_pos = event.y_pos or 0
        img_position = (
            x_pos / self.pixel_size - self.img_size[0] / 2,
            x_pos / self.pixel_size + self.img_size[0] / 2,
            y_pos / self.pixel_size - self.img_size[1] / 2,
            y_pos / self.pixel_size + self.img_size[1] / 2,
        )
        camera_rect = [
            self.view_rect[0][0],
            self.view_rect[0][0] + self.view_rect[1][0],
            self.view_rect[0][1],
            self.view_rect[0][1] + self.view_rect[1][1],
        ]
        if camera_rect[0] > img_position[0]:
            camera_rect[0] = img_position[0]
        if camera_rect[1] < img_position[1]:
            camera_rect[1] = img_position[1]
        if camera_rect[2] > img_position[2]:
            camera_rect[2] = img_position[2]
        if camera_rect[3] < img_position[3]:
            camera_rect[3] = img_position[3]
        self.view_rect = (
            (camera_rect[0], camera_rect[2]),
            (camera_rect[1] - camera_rect[0], camera_rect[3] - camera_rect[2]),
        )
        print(self.view_rect)

    def complement_indices(self, index: Mapping[str, int]) -> dict:
        """MDAEvents not always have all the dimensions, complement."""
        indices = dict(copy.deepcopy(dict(index)))
        for i in DIMENSIONS:
            if i not in indices:
                indices[i] = 0
        return indices

    def _disconnect(self) -> None:
        if self._mmc:
            self._mmc.mda.events.sequenceStarted.disconnect(self.sequenceStarted)
        self.datastore.frame_ready.disconnect(self.frameReady)

    def _reload_position(self) -> None:
        self.qt_settings = QtCore.QSettings("pymmcore_plus", self.__class__.__name__)
        self.resize(self.qt_settings.value("size", QtCore.QSize(270, 225)))
        self.move(self.qt_settings.value("pos", QtCore.QPoint(50, 50)))
        self.cmap_names = self.qt_settings.value("cmaps", ["gray", "cyan", "magenta"])

    def _collapse_view(self) -> None:
        view_rect = (
            (
                self.view_rect[0][0] - self.img_size[0] / 2,
                self.view_rect[0][1] + self.img_size[1] / 2,
            ),
            self.view_rect[1],
        )
        self.view.camera.rect = view_rect

    def closeEvent(self, e: QCloseEvent) -> None:
        """Write window size and position to config file."""
        self.qt_settings.setValue("size", self.size())
        self.qt_settings.setValue("pos", self.pos())
        self.qt_settings.setValue("cmaps", self.cmap_names)
        super().closeEvent(e)

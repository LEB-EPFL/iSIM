from pymmcore_plus import CMMCorePlus
from threading import Thread
import multiprocessing

from qtpy.QtWidgets import QApplication

from isim_control.gui.dark_theme import set_dark
from isim_control.settings_translate import useq_from_settings, load_settings
from isim_control.io.remote_datastore import RemoteDatastore
from isim_control.io.ome_tiff_writer import OMETiffWriter
from isim_control.gui.save_button import SaveButton
from isim_control.pubsub import Subscriber
from pymmcore_widgets._mda._stack_viewer import StackViewer
from useq import MDAEvent
from .pubsub import Publisher, Broker

from _queue import Empty
class RemoteBroker(Broker):
    def run(self):
        while True:
            try:
                message = self.pub_queue.get(timeout=0.5)
                print(message)
                self.route(message["topic"], message["event"], message["values"])
            except Empty:
                if self.stop_requested:
                    break
                else:
                    continue

class Relay(Thread):

    def __init__(self):
        super().__init__()
        self.pub_queue = multiprocessing.Queue()
        self.out_conn, self.in_conn = multiprocessing.Pipe()
        self.pub = Publisher(self.pub_queue)

def writer_process(queue, settings, mm_config, out_conn, name):
    broker = Broker(pub_queue=queue, auto_start=False)
    datastore = RemoteDatastore(name)
    writer = OMETiffWriter(settings["path"], datastore, settings, mm_config)
    broker.attach(writer)
    out_conn.send(True)
    broker.start()


class RemoteViewer(StackViewer):
    def __init__(self, datastore, size, transform):
        super().__init__(datastore=datastore, size=size, transform=transform)
        self.sub = Subscriber(["datastore"], {"new_frame": [self.frameReady],
                                              "reset": [self.on_sequence_start],})

    def on_sequence_start(self, settings: dict, size) -> None:
        seq = useq_from_settings(settings)
        super().on_sequence_start(seq)

    def frameReady(self, event: dict, shape, idx, meta) -> None:
        img = self.datastore.get_frame(idx, shape[0], shape[1])
        event = MDAEvent(**event)
        indices = self.complement_indices(event.index)
        display_indices = self._set_sliders(indices)
        if display_indices == indices:
            self.display_image(img, indices.get("c", 0), indices.get("g", 0))
            # Handle Autoscaling
            clim_slider = self.channel_row.boxes[indices["c"]].slider
            clim_slider.setRange(
                min(clim_slider.minimum(), int(img.min())), max(clim_slider.maximum(),
                                                                int(img.max()))
            )
            if self.channel_row.boxes[indices["c"]].autoscale_chbx.isChecked():
                clim_slider.setValue(
                    [min(clim_slider.minimum(), img.min()), max(clim_slider.maximum(), img.max())]
                )
            self.on_clim_timer(indices["c"])

    def on_display_timer(self) -> None:
        """Update display, usually triggered by QTimer started by slider click."""
        pass
        # old_index = self.display_index.copy()
        # for slider in self.sliders:
        #     self.display_index[slider.name] = slider.value()
        # if old_index == self.display_index:
        #     return
        # if (sequence := self.sequence) is None:
        #     return
        # for g in range(sequence.sizes.get("g", 1)):
        #     for c in range(sequence.sizes.get("c", 1)):
        #         frame = self.datastore.get_frame(
        #             (self.display_index["t"], self.display_index["z"], c, g)
        #         )
        #         self.display_image(frame, c, g)
        # self._canvas.update()


def viewer_process(queue, name):
    app = QApplication([])

    set_dark(app)
    broker = Broker(pub_queue=queue, auto_start=False)
    datastore = RemoteDatastore(name)
    view_settings = load_settings("live_view")
    transform = (view_settings.get("rot", 0),
                 view_settings.get("mirror_x", False),
                 view_settings.get("mirror_y", True))
    viewer = RemoteViewer(datastore=datastore, size=(2048, 2048), transform = transform)
    broker.attach(viewer)
    broker.start()
    # save_button = SaveButton(self.datastore, self.viewer.sequence, self.settings,
    #                                 self.mmc.getSystemState().dict())
    # viewer.bottom_buttons.addWidget(self.save_button)
    viewer.show()
    app.exec_()
    print("Viewer process closing")
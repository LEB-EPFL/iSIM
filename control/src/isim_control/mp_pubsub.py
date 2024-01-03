from threading import Thread
import multiprocessing
import zarr
import numpy as np
import time
import os

from qtpy.QtWidgets import QApplication

from isim_control.gui.dark_theme import set_dark
from isim_control.settings_translate import useq_from_settings, load_settings
from isim_control.io.remote_datastore import RemoteDatastore
from isim_control.io.ome_tiff_writer import OMETiffWriter

from isim_control.pubsub import Subscriber, Publisher, Broker

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import OMEZarrWriter
from pymmcore_widgets._mda._stack_viewer import StackViewer
from useq import MDAEvent, MDASequence
from psygnal import Signal

class Relay(Thread):

    def __init__(self, mmcore: CMMCorePlus|None = None):
        super().__init__()
        self.pub_queue = multiprocessing.Queue()
        self.out_conn, self.in_conn = multiprocessing.Pipe()
        self.pub = Publisher(self.pub_queue)

        if mmcore:
            self._mmc = mmcore
            self._mmc.mda.events.sequenceStarted.connect(self.sequenceStarted)
            self._mmc.mda.events.sequenceFinished.connect(self.sequenceFinished)

    def sequenceStarted(self, seq: MDASequence) -> None:
        self.pub.publish("sequence", "sequence_started", [seq])

    def sequenceFinished(self, seq: MDASequence) -> None:
        self.pub.publish("sequence", "sequence_finished", [seq])


def tiff_writer_process(queue, settings, mm_config, out_conn, name):
    broker = Broker(pub_queue=queue, auto_start=False)
    datastore = RemoteDatastore(name)
    writer = OMETiffWriter(settings["path"], datastore, settings, mm_config)
    broker.attach(writer)
    out_conn.send(True)
    broker.start()

class RemoteZarrWriter(OMEZarrWriter):
    """OMEZarrWriter that runs in a separate process. Communication therefore has to be in basic
    datatypes. This translates them to the needed types and sends out events.
    """
    frame_ready = Signal(MDAEvent)
    def __init__(self, datastore: RemoteDatastore, pub_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sub = Subscriber(["datastore", "sequence"], {"new_frame": [self.frameReady],
                                              "sequence_started": [self.sequence_started],
                                              "sequence_finished": [self.sequence_finished]})
        self.datastore = datastore
        self.pub = Publisher(pub_queue)

    def frameReady(self, event: dict, shape: tuple[int, int], idx: int, meta: dict) -> None:
        img = self.datastore.get_frame(idx, shape[0], shape[1])
        print("GOT FRAME, Writing")
        super().frameReady(img, MDAEvent(**event), meta)
        print("SENDING FRAME READY")
        self.pub.publish("writer", "frame_ready", [event, img.shape, idx, meta])
        self.frame_ready.emit(MDAEvent(**event))

    def sequence_started(self, seq: MDASequence) -> None:
        self._used_axes = tuple(seq.used_axes)
        self.pub.publish("writer", "sequence_started", [seq]) # Make sure viewer also get's the event
        super().sequenceStarted(seq)

    def sequence_finished(self, seq: MDASequence) -> None:
        self.pub.publish("writer", "sequence_finished", [seq])
        super().sequenceFinished(seq)

    def get_frame(self, event: MDAEvent) -> np.ndarray:
        key = f'p{event.index.get("p", 0)}'
        ary = self._arrays[key]
        index = tuple(event.index.get(k) for k in self._used_axes)
        data: np.ndarray = ary[index]
        return data

def zarr_writer_process(queue, settings, mm_config, out_conn, name,
                        make_viewer=False):
    broker = Broker(pub_queue=queue, auto_start=False)
    datastore = RemoteDatastore(name)
    writer = RemoteZarrWriter(datastore, queue, store=settings["path"], overwrite=True)
    broker.attach(writer)
    if make_viewer:
        view_process = multiprocessing.Process(target=viewer_only_process,
                                            args=([queue,
                                                   out_conn,
                                                   settings['path']]))
    view_process.start()
    out_conn.send(True)
    broker.start()


class RemoteZarrStorage:

    frame_ready = Signal(MDAEvent)
    def __init__(self, path):
        self.store = zarr.open(path, mode='r')
        self.sub = Subscriber(["writer"], {"frame_ready": [self.frameReady]})

    def frameReady(self, event: dict, shape: tuple[int, int], idx: int, meta: dict) -> None:
        self.frame_ready.emit(MDAEvent(**event))

    def get_frame(self, event):
        index = tuple(event.index.get(k) for k in event.index.keys())
        data = self.store['p0'][index[:-2]]
        return data


class RemoteViewer(StackViewer):
    def __init__(self, size, transform, datastore):
        super().__init__(size=size, transform=transform, datastore=datastore)
        self.sub = Subscriber(["writer", "sequence"], {"frame_ready": [self.on_frame_ready],
                                              "sequence_started": [self.on_sequence_start],})

    def on_frame_ready(self, event: dict, shape: tuple[int, int], idx: int, meta: dict) -> None:
        return super().frameReady(MDAEvent(**event))


def viewer_only_process(viewer_queue, out_pipe, name=None):
    app = QApplication([])

    set_dark(app)
    broker = Broker(pub_queue=viewer_queue, auto_start=False)
    if os.path.isfile(name) or os.path.isdir(name):
        datastore = RemoteZarrStorage(name)
    else:
        remote_datastore = RemoteDatastore(name)
        datastore = RemoteZarrWriter(remote_datastore, viewer_queue, store=None, overwrite=True)

    view_settings = load_settings("live_view")
    transform = (view_settings.get("rot", 0),
                 view_settings.get("mirror_x", False),
                 view_settings.get("mirror_y", True))
    viewer = RemoteViewer(size=(2048, 2048), transform=transform, datastore=datastore)

    broker.attach(viewer)
    broker.attach(datastore)
    broker.start()

    # save_button = SaveButton(self.datastore, self.viewer.sequence, self.settings,
    #                                 self.mmc.getSystemState().dict())
    # viewer.bottom_buttons.addWidget(self.save_button)
    viewer.show()
    out_pipe.send(True)
    app.exec_()
    print("Viewer process closing")


if __name__ == "__main__":

    from pymmcore_plus import CMMCorePlus
    from useq import MDASequence
    from isim_control.io.buffered_datastore import BufferedDataStore
    from isim_control.settings import iSIMSettings

    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()
    mmc.setProperty("Camera", "OnCameraCCDXSize", 2048)
    mmc.setProperty("Camera", "OnCameraCCDYSize", 2048)

    settings = iSIMSettings(time_plan={"interval": 0.2, "loops": 20}, channels=
                            ({"config": "DAPI", "exposure": 100},{"config": "FITC"}))
    settings["path"] = "C:/Users/stepp/Desktop/test.zarr"


    # Only viewer with own remote Datastore in same process
    # viewer_relay = Relay(mmc)
    # buffered_datastore = BufferedDataStore(mmcore=mmc, create=True,
    #                                        publishers= [viewer_relay.pub])#[writer_relay.pub, viewer_relay.pub])
    # view_process = multiprocessing.Process(target=viewer_only_process,
    #                                         args=([viewer_relay.pub_queue,
    #                                                viewer_relay.out_conn,
    #                                                buffered_datastore._shm.name]))
    # view_process.start()
    # viewer_relay.in_conn.recv()

    # mmc.mda.run(useq_from_settings(settings))
    # viewer_relay.pub.publish("stop", "stop", [])
    print("STOP SIGNAL SENT")

    time.sleep(1)

    # Viewer and Zarr Writer in different processes, viewer launched from writer process
    writer_relay = Relay(mmc)
    buffered_datastore = BufferedDataStore(mmcore=mmc, create=True,
                                           publishers= [writer_relay.pub])
    writer_process = multiprocessing.Process(target=zarr_writer_process,
                                            args=([writer_relay.pub_queue,
                                                settings,
                                                mmc.getSystemState().dict(),
                                                writer_relay.out_conn,
                                                buffered_datastore._shm.name,
                                                {"make_viewer": True}]))
    writer_process.start()
    writer_relay.in_conn.recv()

    time.sleep(5)
    mmc.run_mda(useq_from_settings(settings))
    writer_relay.pub.publish("stop", "stop", [])
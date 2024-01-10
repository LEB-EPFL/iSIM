from threading import Thread
import multiprocessing
import zarr
import numpy as np
import time
import os
from pathlib import Path

from qtpy.QtWidgets import QApplication


from isim_control.gui.dark_theme import set_dark
from isim_control.settings_translate import useq_from_settings, load_settings
from isim_control.io.remote_datastore import RemoteDatastore
from isim_control.io.ome_tiff_writer import OMETiffWriter
from isim_control.gui.assets.save_button import SaveButton

from isim_control.pubsub import Subscriber, Publisher, Broker

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda.handlers import OMEZarrWriter
from pymmcore_widgets._mda._stack_viewer import StackViewer
from useq import MDAEvent, MDASequence
from psygnal import Signal

class Relay(Thread):

    def __init__(self, mmcore: CMMCorePlus|None = None, subscriber: bool = False):
        super().__init__()
        self.pub_queue = multiprocessing.Queue()
        self.out_conn, self.in_conn = multiprocessing.Pipe()
        self.pub = Publisher(self.pub_queue)
        self.settings = None
        if subscriber:
            self.sub = Subscriber(["control"],
                              {"set_relative_xy_position": [self._set_relative_xy_position],})

        if mmcore:
            self._mmc = mmcore
            self._mmc.mda.events.sequenceStarted.connect(self.sequenceStarted)
            self._mmc.mda.events.sequenceFinished.connect(self.sequenceFinished)
            self._mmc.events.XYStagePositionChanged.connect(self.XYStagePositionChanged)
            self.system_state = self._mmc.getSystemState().dict()

    def new_settings(self, settings:dict) -> None:
        self.settings = settings
        if self._mmc:
            self.system_state = self._mmc.getSystemState().dict()

    def sequenceStarted(self, seq: MDASequence) -> None:
        if self._mmc:
            self.pub.publish("sequence", "sequence_started", [seq,
                                                              self.system_state,
                                                              self.settings])
        else:
            self.pub.publish("sequence", "sequence_started", [seq])

    def sequenceFinished(self, seq: MDASequence) -> None:
        self.pub.publish("sequence", "sequence_finished", [seq])

    def XYStagePositionChanged(self, name:str, x: float, y: float) -> None:
        self.pub.publish("sequence", "xy_stage_position_changed", [name, x, y])

    def _set_relative_xy_position(self, device: str, x: float, y: float) -> None:
        self._mmc.setRelativeXYPosition(device, x, y)


class RemoteOMETiffWriter(OMETiffWriter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, subscriber=False, **kwargs)
        self.sub = Subscriber(["datastore"], {"reset": [self.reset],
                                              "new_frame": [self.frameReady],})

    def reset(self, settings, mm_config):
        print("Resetting writer", settings["path"])
        self._folder = Path(settings["path"])
        self._settings = settings
        self._mm_config = mm_config
        self._set_sequence(useq_from_settings(settings))


def tiff_writer_process(queue, settings, mm_config, in_conn, name):
    datastore = RemoteDatastore(name)
    writer = RemoteOMETiffWriter(settings["path"], datastore, settings, mm_config)
    print("Writer ready")
    event = in_conn.recv()
    if event:
        broker = Broker(pub_queue=queue, auto_start=False, name="writer_broker")
        broker.attach(writer)
        broker.start()
    else:
        del datastore
        writer.sub.stop()
        del writer
        print("Writer process closing")


class RemoteZarrWriter(OMEZarrWriter):
    """OMEZarrWriter that runs in a separate process. Communication therefore has to be in basic
    datatypes. This translates them to the needed types and sends out events.
    """
    frame_ready = Signal(MDAEvent)
    def __init__(self, datastore: RemoteDatastore, pub_queue=None,
                 zarr_version=2, *args, **kwargs):
        super().__init__(*args, zarr_version=zarr_version, **kwargs)
        self.sub = Subscriber(["datastore", "sequence"], {"new_frame": [self.frameReady],
                                              "sequence_started": [self.sequence_started],
                                              "sequence_finished": [self.sequence_finished]})
        self.datastore = datastore
        self.pub = Publisher(pub_queue) or None

    def frameReady(self, event: dict, shape: tuple[int, int], idx: int, meta: dict) -> None:
        img = self.datastore.get_frame(idx, shape[0], shape[1])
        super().frameReady(img, MDAEvent(**event), meta)
        # self.frame_ready.emit(MDAEvent(**event))
        if self.pub:
            self.pub.publish("writer", "frame_ready", [event, img.shape, idx, meta])

    def sequence_started(self, seq: MDASequence, mm_config: dict, settings:dict) -> None:
        self._used_axes = tuple(seq.used_axes)
        super().sequenceStarted(seq)

    def sequence_finished(self, seq: MDASequence) -> None:
        super().sequenceFinished(seq)

    def get_frame(self, event: MDAEvent) -> np.ndarray:
        key = f'p{event.index.get("p", 0)}'
        ary = self._arrays[key]
        try:
            index = tuple(event.index.get(k) for k in self._used_axes)
        except AttributeError:
            self.sequence_started(event.sequence)
        data: np.ndarray = ary[index]
        return data

def zarr_writer_process(queue, settings, mm_config, out_conn, name, viewer_queue=None):
    broker = Broker(pub_queue=queue, auto_start=False)
    datastore = RemoteDatastore(name)
    writer = RemoteZarrWriter(datastore, viewer_queue, store=settings["path"], overwrite=True)
    broker.attach(writer)
    out_conn.send(True)
    broker.start()


class RemoteZarrStorage:
    frame_ready = Signal(MDAEvent)
    def __init__(self, path):
        self.store = zarr.open(path, mode='r')
        self.sub = Subscriber(["writer", "sequence"], {"frame_ready": [self.frameReady],
                                                       "sequence_started": [self.sequenceStarted],})

    def frameReady(self, event: dict, shape: tuple[int, int], idx: int, meta: dict) -> None:
        self.frame_ready.emit(MDAEvent(**event))

    def sequenceStarted(self, seq: MDASequence) -> None:
        self._used_axes = tuple(seq.used_axes)

    def get_frame(self, event):
        index = tuple(event.index.get(k) for k in self._used_axes)
        data = self.store['p0'][index]
        return data


class RemoteViewer(StackViewer):
    def __init__(self, size, transform, datastore):
        super().__init__(size=size, transform=transform, datastore=datastore, save_button=False)
        self.save_button = SaveButton(datastore)
        self.bottom_buttons.addWidget(self.save_button)
        self.sub = Subscriber(["writer", "gui"], {"frame_ready": [self.on_frame_ready],
                                              "acquisition_start": [self.on_sequence_start,
                                                                    self.save_button.sequenceStarted],
                                              "shutdown": [self.close_me]})

    def on_frame_ready(self, event: dict, shape: tuple[int, int], idx: int, meta: dict) -> None:
        return super().frameReady(MDAEvent(**event))

    def on_sequence_start(self, seq: MDASequence, *_) -> None:
        return super().on_sequence_start(seq)

    def close_me(self) -> None:
        print("VIEWER ASKED TO CLOSE")
        self.hide()
        self.sub.stop()
        self.close()


def viewer_process(viewer_queue, in_pipe, out_pipe, name=None):
    app = QApplication([])

    set_dark(app)
    if os.path.isfile(name) or os.path.isdir(name):
        # There is a zarr writer writing to a file, viewer will get data from there
        datastore = RemoteZarrStorage(name)
    else:
        # name is the name of a shared memory buffer, viewer will get data from there
        remote_datastore = RemoteDatastore(name)
        datastore = RemoteZarrWriter(remote_datastore, viewer_queue,
                                     store=None, overwrite=True)

    view_settings = load_settings("live_view")
    transform = (view_settings.get("rot", 0),
                 view_settings.get("mirror_x", False),
                 view_settings.get("mirror_y", True))
    viewer = RemoteViewer(size=(2048, 2048), transform=transform, datastore=datastore)
    viewer.pixel_size = 0.056
    out_pipe.send(int(viewer.winId()))

    event = in_pipe.recv()
    if event:
        broker = Broker(pub_queue=viewer_queue, auto_start=False, name="viewer_broker")
        broker.attach(viewer)
        broker.attach(datastore)
        broker.start()
        viewer.show()
        app.exec_()
        broker.stop()
        print("Viewer process closing")
        app.exit()
    else:
        del remote_datastore
        datastore.sub.stop()
        del datastore
        viewer.close_me()
        del viewer
        print("Viewer process closing")
        app.exit()


if __name__ == "__main__":

    from pymmcore_plus import CMMCorePlus
    from useq import MDASequence
    from isim_control.io.buffered_datastore import BufferedDataStore
    from isim_control.settings import iSIMSettings

    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()
    size = 2048
    mmc.setProperty("Camera", "OnCameraCCDXSize", size)
    mmc.setProperty("Camera", "OnCameraCCDYSize", size)

    settings = iSIMSettings(time_plan={"interval": 0.25, "loops": 200}, channels=
                            ({"config": "DAPI", "exposure": 100},{"config": "FITC"}))
    settings["path"] = "C:/Users/stepp/Desktop/test.zarr"


    ## Only viewer with own remote Datastore in same process
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
    # print("STOP SIGNAL SENT")

    # time.sleep(1)

    ## Viewer and Zarr Writer in different processes, viewer using writer location for data
    # writer_relay = Relay(mmc)
    # viewer_relay = Relay(mmc)
    # buffered_datastore = BufferedDataStore(mmcore=mmc, create=True,
    #                                        publishers= [writer_relay.pub])
    # writer_process = multiprocessing.Process(target=zarr_writer_process,
    #                                         args=([writer_relay.pub_queue,
    #                                             settings,
    #                                             mmc.getSystemState().dict(),
    #                                             writer_relay.out_conn,
    #                                             buffered_datastore._shm.name]),
    #                                         kwargs=
    #                                             {"viewer_queue": viewer_relay.pub_queue})

    # viewer_process = multiprocessing.Process(target=viewer_only_process,
    #                                     args=([viewer_relay.pub_queue,
    #                                            viewer_relay.out_conn,
    #                                            settings['path']]))

    # writer_process.start()
    # writer_relay.in_conn.recv()
    # viewer_process.start()
    # viewer_relay.in_conn.recv()

    # mmc.mda.run(useq_from_settings(settings))
    # time.sleep(2)
    # while mmc.isSequenceRunning():
    #     time.sleep(1)
    # print("Sending stop")
    # writer_relay.pub.publish("stop", "stop", [])
    # viewer_relay.pub.publish("stop", "stop", [])

    ## Viewer without writer and additional process for a tiff writer
    writer_relay = Relay(mmc)
    viewer_relay = Relay(mmc)
    settings["path"] = "C:/Users/stepp/Desktop/test"
    buffered_datastore = BufferedDataStore(mmcore=mmc, create=True, publishers=[writer_relay.pub,
                                                                                viewer_relay.pub])
    writer_process = multiprocessing.Process(target=tiff_writer_process,
                                            args=([writer_relay.pub_queue,
                                                settings,
                                                mmc.getSystemState().dict(),
                                                writer_relay.out_conn,
                                                buffered_datastore._shm.name]))
    viewer_process = multiprocessing.Process(target=viewer_only_process,
                                            args=([viewer_relay.pub_queue,
                                                   viewer_relay.out_conn,
                                                   buffered_datastore._shm.name]))

    writer_process.start()
    viewer_process.start()
    viewer_relay.in_conn.recv()
    writer_relay.in_conn.recv()


    mmc.mda.run(useq_from_settings(settings))
    time.sleep(2)
    while mmc.isSequenceRunning():
        time.sleep(1)
    print("Sending stop")
    writer_relay.pub.publish("stop", "stop", [])
    viewer_relay.pub.publish("stop", "stop", [])

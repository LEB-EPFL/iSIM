from threading import Thread
import multiprocessing

from qtpy.QtWidgets import QApplication

from isim_control.gui.dark_theme import set_dark
from isim_control.settings_translate import useq_from_settings, load_settings
from isim_control.io.remote_datastore import RemoteDatastore
from isim_control.io.ome_tiff_writer import OMETiffWriter
from isim_control.gui.save_button import SaveButton
from isim_control.pubsub import Subscriber, Publisher, Broker
from pymmcore_plus.mda.handlers import OMEZarrWriter
from pymmcore_widgets._mda._stack_viewer import StackViewer
from useq import MDAEvent


class Relay(Thread):

    def __init__(self):
        super().__init__()
        self.pub_queue = multiprocessing.Queue()
        self.out_conn, self.in_conn = multiprocessing.Pipe()
        self.pub = Publisher(self.pub_queue)

def tiff_writer_process(queue, settings, mm_config, out_conn, name):
    broker = Broker(pub_queue=queue, auto_start=False)
    datastore = RemoteDatastore(name)
    writer = OMETiffWriter(settings["path"], datastore, settings, mm_config)
    broker.attach(writer)
    out_conn.send(True)
    broker.start()

class RemoteZarrWriter(OMEZarrWriter):
    """OMEZarrWriter that runs in a separate process. Communication therefore has to be in basic
    datatypes. This translates them to the needed types.
    """
    def __init__(self, datastore: RemoteDatastore, pub_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sub = Subscriber(["datastore"], {"new_frame": [self.frameReady],
                                              "sequence_started": [self.sequenceStarted],
                                              "sequence_finished": [self.sequenceFinished]})
        self.datastore = datastore
        self.pub = Publisher(pub_queue)

    def frameReady(self, event: dict, shape: tuple[int, int], idx: int, meta: dict) -> None:
        img = self.datastore.get_frame(idx, shape[0], shape[1])
        event = MDAEvent(**event)
        super().frameReady(img, event, meta)
        self.pub.publish("writer", "frameReady", [event.model_dump(), img.shape, idx, meta])

    def sequenceStarted(self, settings: dict, size: tuple[int, int]) -> None:
        self.pub.publish("datastore", "reset", [settings]) # Make sure viewer also get's the event
        seq = useq_from_settings(settings)
        super().sequenceStarted(seq)

    def sequenceFinished(self, settings: dict) -> None:
        seq = useq_from_settings(settings)
        super().sequenceFinished(seq)

def zarr_writer_process(queue, pub_queue, settings, mm_config, out_conn, name):
    broker = Broker(pub_queue=queue, auto_start=False)
    datastore = RemoteDatastore(name)
    writer = RemoteZarrWriter(datastore, pub_queue, settings["path"], overwrite=True)
    broker.attach(writer)
    out_conn.send(True)
    broker.start()
    print("WRITER PROCESS STARTED")

import zarr
class RemoteZarrStorage:
    def __init__(self, path):
        print("REMOTE PATH", path)
        self.store = zarr.open(path, mode='r')

    def get_frame(self, index):
        print("ASKING FOR INDEX", index)
        data = self.store.p0[index[:-2]]
        return data


class RemoteViewer(StackViewer):
    def __init__(self, datastore, size, transform):
        super().__init__(size=size, transform=transform)
        self.sub = Subscriber(["writer", "datastore"], {"frameReady": [self.on_frame_ready],
                                              "reset": [self.on_sequence_start],})
        self.datastore = datastore

    def on_frame_ready(self, event: dict, shape: tuple[int, int], idx: int, meta: dict) -> None:
        return super().on_frame_ready(MDAEvent(**event))

    def on_sequence_start(self, settings: dict, size) -> None:
        seq = useq_from_settings(settings)
        super().on_sequence_start(seq)


def viewer_process(viewer_queue, sub_queue, out_pipe, writer_path):
    app = QApplication([])

    set_dark(app)
    broker = Broker(pub_queue=viewer_queue, auto_start=False)
    broker2 = Broker(pub_queue=sub_queue, auto_start=False)
    datastore = RemoteZarrStorage(writer_path)
    view_settings = load_settings("live_view")
    transform = (view_settings.get("rot", 0),
                 view_settings.get("mirror_x", False),
                 view_settings.get("mirror_y", True))
    viewer = RemoteViewer(datastore=datastore, size=(512, 512), transform = transform)
    broker.attach(viewer)
    broker2.attach(viewer)
    broker.start()
    broker2.start()
    # save_button = SaveButton(self.datastore, self.viewer.sequence, self.settings,
    #                                 self.mmc.getSystemState().dict())
    # viewer.bottom_buttons.addWidget(self.save_button)
    viewer.show()
    out_pipe.send(True)
    app.exec_()
    print("Viewer process closing")


if __name__ == "__main__":
    import time
    from pymmcore_plus import CMMCorePlus
    from useq import MDASequence
    from isim_control.io.buffered_datastore import BufferedDataStore
    from isim_control.settings import iSIMSettings

    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration()
    settings = iSIMSettings(time_plan={"interval": 0.5, "loops": 300}, channels=
                            ({"config": "DAPI", "exposure": 100},{"config": "FITC"}))
    settings["path"] = "C:/Users/stepp/Desktop/test.zarr"

    writer_relay = Relay()
    viewer_relay = Relay()
    sub_relay = Relay()

    buffered_datastore = BufferedDataStore(mmcore=mmc, create=True,
                                           publishers=[writer_relay.pub, viewer_relay.pub])

    writer_process = multiprocessing.Process(target=zarr_writer_process,
                                            args=([writer_relay.pub_queue,
                                                   sub_relay.pub_queue,
                                                settings,
                                                mmc.getSystemState().dict(),
                                                writer_relay.out_conn,
                                                buffered_datastore._shm.name]))
    writer_process.start()
    writer_relay.in_conn.recv()
    view_process = multiprocessing.Process(target=viewer_process,
                                            args=([viewer_relay.pub_queue,
                                                   sub_relay.pub_queue,
                                                   viewer_relay.out_conn,
                                                   settings['path']]))
    view_process.start()
    viewer_relay.in_conn.recv()



    viewer_relay.pub.publish("datastore", "reset", [settings, (512, 512)])
    time.sleep(3)
    mmc.mda.run(useq_from_settings(settings))


    writer_relay.pub.publish("stop", "stop", [])
    viewer_relay.pub.publish("stop", "stop", [])
    sub_relay.pub.publish("stop", "stop", [])
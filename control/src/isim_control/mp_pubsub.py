from pymmcore_plus import CMMCorePlus
from useq import MDAEvent
from threading import Thread
import multiprocessing
import numpy as np

from .pubsub import Publisher, Subscriber

class Relay(Thread):

    def __init__(self, mmcore: CMMCorePlus, auto_start: bool = True):
        super().__init__()
        self.mmcore = mmcore
        self.pub_queue = multiprocessing.Queue()
        self.out_conn, self.in_conn = multiprocessing.Pipe()
        self.pub = Publisher(self.pub_queue)
        routes = {"new_frame": [self.new_frame]}
        self.sub = Subscriber(["datastore"], routes)
        self.mmc = mmcore
        self.mmc.mda.events.frameReady.connect(self.frameReady)

    def frameReady(self, frame: np.ndarray, event: MDAEvent, metadata: dict):
        print("NEW FRAME IN RELAY")
        # self.pub.publish("acq", "new_frame", [frame, event.model_dump(), {}])

    def new_frame(self, event: dict, shape: tuple, idx: int, meta: dict):
        self.pub.publish("datastore", "new_frame", [event, shape, idx, meta])
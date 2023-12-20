from pymmcore_plus import CMMCorePlus
from useq import MDAEvent
from threading import Thread
import multiprocessing
import numpy as np

from .pubsub import Publisher

class Relay(Thread):

    def __init__(self, mmcore: CMMCorePlus, auto_start: bool = True):
        super().__init__()
        self.mmcore = mmcore
        self.pub_queue = multiprocessing.Queue()
        self.out_conn, self.in_conn = multiprocessing.Pipe()
        self.pub = Publisher(self.pub_queue)
        self.mmc = mmcore
        self.mmc.mda.events.frameReady.connect(self.frameReady)

    def frameReady(self, frame: np.ndarray, event: MDAEvent, metadata: dict):
        self.pub.publish("acq", "new_frame", [frame, event.model_dump(), {}])

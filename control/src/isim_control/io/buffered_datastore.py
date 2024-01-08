from leb.kpal.buffer import BufferedArray
import copy
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from pymmcore_plus import CMMCorePlus

from useq import MDAEvent
import copy
import time

CAPACITY = int(30E8)

class BufferedDataStore(BufferedArray):
    def __new__(self, *args, **kwargs):
        print(kwargs)
        self.mmc = kwargs.get("mmcore", None)
        self.pubs = kwargs.get('publishers', None)
        self.live_frames = kwargs.get("live_frames", None)
        print(self.live_frames)
        if self.live_frames:
            del kwargs['live_frames']
        if self.mmc:
            del kwargs['mmcore']
        if self.pubs:
            del kwargs['publishers']
        return super().__new__(BufferedDataStore, *args, capacity=CAPACITY, dtype=np.uint16,
                                **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__()
        if self.mmc:
            self.mmc.mda.events.frameReady.connect(self.new_frame)
            if self.live_frames:
                print("LIVE FRAMES CONNECTED")
                self.mmc.events.liveFrameReady.connect(self.new_frame)


    def new_frame(self, img: np.ndarray, event: MDAEvent, meta:dict):
        idx = self._write_idx
        t0 = time.perf_counter()
        self.put(img)
        if this_time:= time.perf_counter() - t0 > 0.1:
            print("SLOW WRITE TO DATASTORE", this_time)
        try:
            del meta['Event']
        except:
            pass
        for pub in self.pubs:
            pub.publish("datastore", "new_frame", [event.model_dump(), img.shape, idx, meta])


if __name__ == "__main__":
    from useq import MDASequence
    import time
    mmcore = CMMCorePlus()
    mmcore.loadSystemConfiguration()
    mmcore.setProperty("Camera", "OnCameraCCDXSize", 1024)
    mmcore.setProperty("Camera", "OnCameraCCDYSize", 1024)
    database = BufferedDataStore(create=True)
    mmcore.run_mda(MDASequence(time_plan={"interval": 1, "loops": 3}))
    time.sleep(3)
    print(database.get_frame([0, 0, 1]).shape)
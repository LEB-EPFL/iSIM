from leb.kpal.buffer import BufferedArray
import copy
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from pymmcore_plus import CMMCorePlus

from useq import MDAEvent
import copy

DIMENSIONS = ["c", "z", "t", "p", "g"]
CAPACITY = int(30E7)

class BufferedDataStore(BufferedArray):
    def __new__(self, *args, **kwargs):
        print(kwargs)
        self.mmc = kwargs.get("mmcore", None)
        self.pub = kwargs.get('publisher', None)
        if self.mmc:
            del kwargs['mmcore']
        if self.pub:
            del kwargs['publisher']
        return super().__new__(BufferedDataStore, *args, capacity=CAPACITY, dtype=np.uint16,
                                **kwargs)

    def __init__(self, *args, **kwargs):
        super().__init__()
        #TODO: This limits the sizes of the axes
        self.indeces_to_idx = np.zeros([1000,1,3, 4, 3], np.uint64)
        if self.mmc:
            self.mmc.mda.events.frameReady.connect(self.new_frame)
            print("MMC EVENT CONNECTED")

    def new_frame(self, img: np.ndarray, event: MDAEvent, meta:dict):
        print("NEW IMAGE IN BUFFEREDSTORE", img.shape)
        idx = self._write_idx
        indices = event.index
        try:
            self.indeces_to_idx[indices.get('t', 0),
                                indices.get('z', 0),
                                indices.get('c', 0),
                                indices.get('g', 0)] = (int(img.shape[0]), int(img.shape[1]), int(idx))
        except IndexError:
            shape_now = self.indeces_to_idx.shape
            new_min_shape = [indices['c'], indices['z'], indices['t']]
            diff = [x - y for x, y in zip(new_min_shape, shape_now)]
            for i, app in enumerate(diff):
                self.indeces_to_idx.append(i, app)
            print("New shape for indeces:", self.indeces_to_idx.shape)
        self.put(img)
        meta_dict = dict({key: value for key, value in meta.items() if key not in ['Event'] })
        self.pub.publish("datastore", "new_frame", [event.model_dump(), img.shape, idx, meta_dict])

    def get_frame(self, indeces: list):
        width, height, index = self.indeces_to_idx[*indeces]
        index1 = index + width*height
        return np.reshape(self[index:index1], [width, height])


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

from .buffered_datastore import BufferedDataStore
from useq import MDAEvent
import numpy as np

class RemoteDatastore():
    def __init__(self, remote_datastore_name):
        self.remote = BufferedDataStore(name=remote_datastore_name, create=False)
        self.dtype = self.remote.dtype

    def get_frame(self, index: int, width: int, height:int):
        index1 = index + width*height
        if index1 > self.remote.shape[0]:
            data = self.remote.take(range(index,index1), mode='wrap')
        else:
            data = self.remote[index:index1]
        return np.reshape(data, [width, height])
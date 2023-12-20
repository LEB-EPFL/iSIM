
from .buffered_datastore import BufferedDataStore
from useq import MDAEvent
import numpy as np

class RemoteDatastore():
    def __init__(self, remote_datastore_name):
        self.remote = BufferedDataStore(name=remote_datastore_name, create=False)

    def get_frame(self, index: int, width: int, height:int):
        index1 = index + width*height
        return np.reshape(self.remote[index:index1], [width, height])
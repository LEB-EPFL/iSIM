from pymmcore_plus import CMMCorePlus
import useq
from gui.hardware.nidaq_components.devices import AOTF
import numpy as np

class NISettings():
    def __init__(self, mmcore:CMMCorePlus = None, sample_rate: int = 48000):
        self.mmcore = mmcore or CMMCorePlus.instance()
        self.sample_rate = sample_rate

        self.mmcore.mda.events.sequenceStarted.connect(self.on_sequence_start)

        self.get_settings()

    def get_settings(self):
        camera = self.mmcore.getCameraDevice()
        readout = self.mmcore.getProperty(camera, "Timing-ReadoutTimeNs")
        self.camera_readout_time = float(readout)/1e9
        print("Camera readout time:", self.camera_readout_time)
        self.camera_exposure_time = float(self.mmcore.getExposure())/1000
        self.real_exposure_time = self.camera_exposure_time - self.camera_readout_time
        self.real_exposure_points = int(np.floor(self.real_exposure_time*self.sample_rate))
        self.readout_points = int(np.floor(self.camera_readout_time*self.sample_rate))
        self.total_points = self.real_exposure_points + self.readout_points

    def on_sequence_start(self, event):
        self.get_settings()

import useq
import numpy as np
import matplotlib.pyplot as plt
import time

from control.ni.devices import AOTF, Camera, Galvo, Twitcher, Stage, LED
from settings import iSIMSettings

class NIDeviceGroup():
    def __init__(self, settings: dict):

        self.galvo = Galvo()
        self.camera = Camera()
        self.aotf = AOTF()
        self.twitcher = Twitcher()
        self.stage = Stage()
        self.led = LED()
        self.settings = settings

    def get_data(self, event: useq.MDAEvent, next_event: useq.MDAEvent|None = None):
        galvo = self.galvo.one_frame(self.settings)[:-self.settings['readout_points']//3]
        stage = self.stage.one_frame(self.settings, event, next_event)[:-self.settings['readout_points']//3]
        camera = self.camera.one_frame(self.settings)[:-self.settings['readout_points']//3]
        aotf = self.aotf.one_frame(self.settings, event)[:, :-self.settings['readout_points']//3]
        led = self.led.one_frame(self.settings, event)[:, :-self.settings['readout_points']//3]
        twitcher = self.twitcher.one_frame(self.settings)[:-self.settings['readout_points']//3]
        return np.vstack([galvo, stage, camera, aotf, led, twitcher])

    def plot(self):
        event = useq.MDAEvent(channel={"config": "488"}, z_pos=2)
        event2 = useq.MDAEvent(channel={"config": "488"}, z_pos=5)
        t0 = time.perf_counter()
        data = self.get_data(event, event2)
        print("Time to get data:", time.perf_counter() - t0)
        for device in data:
            plt.step(np.arange(len(device)), device)
        plt.show()


if __name__ == "__main__":
    from pymmcore_plus import CMMCorePlus
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration("C:/iSIM/Micro-Manager-2.0.2/prime_only.cfg")
    mmc.setCameraDevice("Prime")
    mmc.setExposure(100)
    mmc.setProperty("Prime", "TriggerMode", "Edge Trigger")
    settings = iSIMSettings()
    event = useq.MDAEvent(channel={"config": "488"}, metadata={'power':50})
    event = useq.MDAEvent(channel={"config": "488"}, z_pos=2)
    event2 = useq.MDAEvent(channel={"config": "488"}, z_pos=5)
    frame = iSIMSettings(settings)
    data = frame.get_data(event)
    frame.plot()

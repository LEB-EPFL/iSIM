from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import mda_listeners_connected
from isim_control.pubsub import Subscriber, Publisher
from isim_control.settings import iSIMSettings
from isim_control.ni import live, acquisition, devices
from isim_control.settings_translate import useq_from_settings

import time
from threading import Timer

class iSIMRunner:
    def __init__(self, mmcore: CMMCorePlus, live_engine: live.LiveEngine,
                 acquisition_engine: acquisition.AcquisitionEngine, devices: devices.NIDeviceGroup,
                 settings: iSIMSettings = None, publisher: Publisher = None):
        self.mmc = mmcore
        routes = {"live_button_clicked": [self._on_live_toggle],
                  "snap_button_clicked": [self._on_snap],
                  "acquisition_start": [self._on_acquisition_start],
                  "acquisition_pause": [self._on_acquisition_pause],
                  "acquisition_cancel": [self._on_acquisition_cancel],
                  "settings_change": [self._on_settings_change]
                  }
        self.sub = Subscriber(["gui"], routes)
        self.pub = publisher
        self.last_restart = 0

        self.settings = settings or iSIMSettings()
        self.live_engine = live_engine
        self.acquisition_engine = acquisition_engine
        self.devices = devices

        self.mmc.mda.events.sequenceFinished.connect(self._on_acquisition_finished)
        self.mmc.events.propertyChanged.connect(self._restart_live)

    def _on_acquisition_finished(self):
        self.pub.publish("gui", "acquisition_finished")

    def _on_acquisition_cancel(self):
        self.mmc.mda.cancel()

    def _on_acquisition_pause(self, toggled):
        self.mmc.mda.toggle_pause()

    def _on_acquisition_start(self, toggled):
        if self.live_engine.timer:
            self.live_engine._on_sequence_stopped()
            self.pub.publish("gui", "live_button_clicked", [False])
            time.sleep(1)
        self.settings['ni']['relative_z'] = self.mmc.getPosition()
        self.settings.calculate_ni_settings(self.settings['acquisition']['channels'][0]['exposure'])
        self.devices.update_settings(self.settings)
        self.acquisition_engine.update_settings(self.settings)
        self.acquisition_engine.adjust_camera_exposure(self.settings['camera']['exposure']*1000)
        self.mmc.run_mda(useq_from_settings(self.settings))

    def _on_live_toggle(self, toggled):
        if self.acquisition_engine.running.is_set():
            return
        if toggled:
            self.settings.calculate_ni_settings(self.settings['live']['exposure'])
            self.devices.update_settings(self.settings)
            self.live_engine.update_settings(self.settings)
            self.live_engine._on_sequence_started()
        else:
            self.live_engine._on_sequence_stopped()

    def _on_snap(self, *_):
        if self.acquisition_engine.running.is_set():
            return
        self.settings.calculate_ni_settings(self.settings['live']['exposure'])
        self.devices.update_settings(self.settings)
        self.live_engine.update_settings(self.settings)
        self.live_engine.snap()

    def _restart_live(self, device, *_):
        """Once a second restart live if property has changed"""
        #TODO: should this go into LiveEngine?
        if time.perf_counter() - self.last_restart < 1:
            print(device, " changed!")
            self.mmc.waitForDevice(device)
            self.live_engine.restart()
        self.last_restart = time.perf_counter()

    def _on_settings_change(self, keys, value):
        orig_live_exposure = self.settings['live']['exposure']
        self.settings.set_by_path(keys, value)
        if keys == ['live', 'exposure'] and orig_live_exposure != value:
            restart = False
            self.settings.calculate_ni_settings(value)
            if self.live_engine.timer:
                self.live_engine._on_sequence_stopped()
                restart = True
            self.mmc.setExposure(self.settings['camera']['exposure']*1000)
            self.mmc.waitForDevice(self.mmc.getCameraDevice())
            print("EXPOSURE SET", self.mmc.getExposure())
            self.devices.update_settings(self.settings)
            self.live_engine.update_settings(self.settings)
            if restart:
                Timer(0.5, self.live_engine._on_sequence_started).start()
        self.live_engine.update_settings(self.settings)
        self.acquisition_engine.update_settings(self.settings)

    def stop(self):
        self.sub.stop()

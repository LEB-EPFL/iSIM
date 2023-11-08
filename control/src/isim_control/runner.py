from pymmcore_plus import CMMCorePlus
from isim_control.pubsub import Subscriber
from isim_control.settings import iSIMSettings
from isim_control.ni import live, acquisition, devices
from isim_control.settings_translate import useq_from_settings


class iSIMRunner:
    def __init__(self, mmcore: CMMCorePlus, live_engine: live.LiveEngine,
                 acquisition_engine: acquisition.AcquisitionEngine, devices: devices.NIDeviceGroup,
                 settings: iSIMSettings = None):
        self.mmc = mmcore or CMMCorePlus.instance()
        routes = {"live_button_clicked": [self._on_live_toggle],
                  "acquisition_button_clicked": [self._on_acquisition_started],
                  "settings_change": [self._on_settings_change]}
        self.sub = Subscriber(["gui"], routes)

        self.settings = settings or iSIMSettings()
        self.live_engine = live_engine
        self.acquisition_engine = acquisition_engine
        self.devices = devices


    def _on_acquisition_started(self, toggled):
        print(f"Broker: acquisition toggled {toggled}")
        if toggled:
            self.devices.update_settings(self.settings)
            self.acquisition_engine.update_settings(self.settings)
            self.mmc.run_mda(useq_from_settings(self.settings))

    def _on_live_toggle(self, toggled):
        print(f"Broker: live toggled {toggled}")
        if toggled:
            self.live_engine.update_settings(self.settings)
            self.live_engine._on_sequence_started()
            # self.mmc.startContinuousSequenceAcquisition()
        else:
            self.live_engine._on_sequence_stopped()
            # self.mmc.stopSequenceAcquisition()

    def _on_settings_change(self, keys, value):
        self.settings.set_by_path(keys, value)
        self.live_engine.update_settings(self.settings)
        self.acquisition_engine.update_settings(self.settings)

    def stop(self):
        self.sub.stop()

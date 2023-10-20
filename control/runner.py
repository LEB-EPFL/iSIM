from pubsub import Subscriber
from pymmcore_plus import CMMCorePlus
from settings import iSIMSettings
from control.ni import live, acquisition, devices
from settings_translate import useq_from_settings


class iSIMRunner:
    def __init__(self, mmcore: CMMCorePlus, live_engine: live.LiveEngine,
                 acquisition_engine: acquisition.AcquisitionEngine, devices: devices.NIDeviceGroup):
        self.mmc = mmcore or CMMCorePlus.instance()
        routes = {"live_button_clicked": [self._on_live_toggle],
                  "acquisition_button_clicked": [self._on_acquisition_started],
                  "settings_change": [self._on_settings_change]}
        self.sub = Subscriber(["gui"], routes)

        self.settings = iSIMSettings()
        self.live_engine = live_engine
        self.acquisition_engine = acquisition_engine
        self.devices = devices

        #TODO: remove this
        self.settings["acquisition"]["time_plan"] = {"interval": 0.5, "loops": 5}

    def _on_acquisition_started(self, toggled):
        print(f"Broker: acquisition toggled {toggled}")
        if toggled:
            self.devices.update_settings(self.settings['ni'])
            self.acquisition_engine.update_settings(self.settings)
            self.mmc.run_mda(useq_from_settings(self.settings))

    def _on_live_toggle(self, toggled):
        print(f"Broker: live toggled {toggled}")
        if toggled:
            self.live_engine.update_settings(self.settings['live'])
            self.mmc.startContinuousSequenceAcquisition()
        else:
            self.mmc.stopSequenceAcquisition()

    def _on_settings_change(self, keys, value):
        print(f"Broker: settings changed {keys} to {value}")
        self.settings.set_by_path(keys, value)
        if "live" in keys:
            self.live_engine.update_settings(self.settings['live'])

    def stop(self):
        self.sub.stop()
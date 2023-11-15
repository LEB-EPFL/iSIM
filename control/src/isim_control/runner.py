from pymmcore_plus import CMMCorePlus
from pymmcore_plus.mda import mda_listeners_connected
from isim_control.pubsub import Subscriber, Publisher
from isim_control.settings import iSIMSettings
from isim_control.ni import live, acquisition, devices
from isim_control.settings_translate import useq_from_settings


class iSIMRunner:
    def __init__(self, mmcore: CMMCorePlus, live_engine: live.LiveEngine,
                 acquisition_engine: acquisition.AcquisitionEngine, devices: devices.NIDeviceGroup,
                 settings: iSIMSettings = None, publisher: Publisher = None):
        self.mmc = mmcore or CMMCorePlus.instance()
        routes = {"live_button_clicked": [self._on_live_toggle],
                  "acquisition_start": [self._on_acquisition_start],
                  "acquisition_pause": [self._on_acquisition_pause],
                  "acquisition_cancel": [self._on_acquisition_cancel],
                  "settings_change": [self._on_settings_change]}
        self.sub = Subscriber(["gui"], routes)
        self.pub = publisher

        self.settings = settings or iSIMSettings()
        self.live_engine = live_engine
        self.acquisition_engine = acquisition_engine
        self.devices = devices

        self.mmc.mda.events.sequenceFinished.connect(self._on_acquisition_finished)
        self.mmc.events.configSet.connect(self._restart_live)

    def _on_acquisition_finished(self):
        self.pub.publish("gui", "acquisition_finished")

    def _on_acquisition_cancel(self):
        self.mmc.mda.cancel()

    def _on_acquisition_pause(self, toggled):
        self.mmc.mda.toggle_pause()

    def _on_acquisition_start(self, toggled):
        print(f"Broker: acquisition toggled {toggled}")
        self.settings['ni']['relative_z'] = self.mmc.getPosition()
        self.devices.update_settings(self.settings)
        self.acquisition_engine.update_settings(self.settings)

        self.mmc.run_mda(useq_from_settings(self.settings))

    def _on_live_toggle(self, toggled):
        print(f"Broker: live toggled {toggled}")
        if toggled:
            self.live_engine.update_settings(self.settings)
            self.live_engine._on_sequence_started()
        else:
            self.live_engine._on_sequence_stopped()

    def _restart_live(self, prop, value):
        print("restart live if necessary")
        self.live_engine.restart()

    def _on_settings_change(self, keys, value):
        self.settings.set_by_path(keys, value)
        self.live_engine.update_settings(self.settings)
        self.acquisition_engine.update_settings(self.settings)

    def stop(self):
        self.sub.stop()

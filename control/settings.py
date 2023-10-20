import numpy as np
from functools import reduce
import operator

class iSIMSettings(dict):
    """Central dict that holds all data necessary to run the iSIM.

    Different components can request views into the dict that are necessary for them to function.
    It includes information for the NIDAQ, pymmcore-plus etc.
    """
    def __init__(
        self,
        laser_powers: dict = {'488': 15, '561': 80},
        use_filters: bool = False,
        relative_z: float = 0.0,
        twitchers: bool = False,
        axis_order: str = "tpgcz",
        time_plan: dict = None,
        channels: (dict) = ({"config": "488", "exposure": 100}, ),
        z_plan: dict = None,
        grid_plan: dict = None,
        camera_name: str = "Prime",
        camera_readout_time: float = 0.029,
        ni_sample_rate: int = 9600,
                 ):
        super().__init__()
        self['use_filters'] = use_filters
        self['relative_z'] = relative_z
        self['twitchers'] = twitchers
        self['acquisition'] = {}
        self['acquisition']['axis_order'] = axis_order
        self['acquisition']['channels'] = channels
        self['exposure_time'] = channels[0]['exposure']/1000
        self['acquisition']['z_plan'] = z_plan
        self['acquisition']['time_plan'] = time_plan
        self['acquisition']['grid_plan'] = grid_plan

        self['camera'] = {}
        self['camera']['name'] = camera_name
        self['camera']['readout_time'] = camera_readout_time

        self['ni'] = {}
        self['ni']['laser_powers'] = laser_powers
        self['ni']['sample_rate'] = ni_sample_rate

        self['live'] = {"channel": "561", "fps": 5, "twitchers": False}
        self['live']['ni'] = {"laser_powers": {'488': 50, '561': 50, 'led': 100}}

        self['live_mode'] = False

        self.calculate_ni_settings()
        self.set_defaults_grid_plan()

    def set_defaults_grid_plan(self):
        if self['acquisition']['grid_plan']:
            self['acquisition']['grid_plan']['fov_width'] = 118
            self['acquisition']['grid_plan']['fov_height'] = 118
            self['acquisition']['grid_plan']['overlap'] = (0.1, 0.1)
            self['acquisition']['grid_plan']['mode'] = "row_wise_snake"
            self['acquisition']['grid_plan']['relative_to'] = 'center'

    def calculate_ni_settings(self):
        self['camera']['exposure'] = (self['acquisition']['channels'][0]['exposure']/1000 +
                                      self['camera']['readout_time'])
        self['ni']['exposure_points'] = int(np.floor(self['exposure_time']
                                                     *self['ni']['sample_rate']))
        self['ni']['readout_points'] = int(np.floor(self['camera']['readout_time']*
                                                    self['ni']['sample_rate']))
        self['ni']['total_points'] = self['ni']['exposure_points'] + self['ni']['readout_points']

    def get_by_path(self, items):
        """Access a nested object by item sequence."""
        return reduce(operator.getitem, items, self)

    def set_by_path(self, items, value):
        """Set a value in a nested object by item sequence."""
        self.get_by_path(items[:-1])[items[-1]] = value


if __name__ == "__main__":
    from ni.devices import NIDeviceGroup
    from settings_translate import useq_from_settings, add_settings_from_core
    from pymmcore_plus import CMMCorePlus
    from pymmcore_widgets import ImagePreview
    import time
    from ni.acquisition import AcquisitionEngine
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration("C:/iSIM/Micro-Manager-2.0.2/prime_only.cfg")
    mmc.setCameraDevice("Prime")
    mmc.setProperty("Prime", "TriggerMode", "Edge Trigger")
    mmc.setProperty("Prime", "ReadoutRate", "100MHz 16bit")
    mmc.setProperty("Sapphire", "State", 1)
    mmc.setProperty("Laser", "Laser Operation", "On")
    mmc.setAutoShutter(False)
    time.sleep(1)

    from qtpy.QtWidgets import QApplication
    app = QApplication([])
    preview = ImagePreview(mmcore=mmc)
    mmc.mda.events.frameReady.connect(preview._on_image_snapped)
    preview.show()

    acq = iSIMSettings(
        time_plan = {"interval": 0.15, "loops": 10}
        )
    acq = add_settings_from_core(mmc, acq)
    acq.calculate_ni_settings()


    devices = NIDeviceGroup(acq['ni'])
    seq = useq_from_settings(acq)
    # mmc.setExposure((acq['exposure_time'] - acq['camera']['readout_time'])*1000)
    EXPOSURE = (acq['exposure_time'] + acq['camera']['readout_time'])*1000
    mmc.setExposure(EXPOSURE)
    print("Effective camera exposure", EXPOSURE)

    engine = AcquisitionEngine(mmc, devices, acq)
    # print(engine.task.timing.samp_clk_rate)
    mmc.mda.set_engine(engine)
    time.sleep(2)
    mmc.run_mda(seq)
    app.exec_()

    # import matplotlib.pyplot as plt
    # data = devices.get_data(next(seq.iter_events()))
    # for device in data:
    #     plt.step(np.arange(len(device))/acq['ni']['sample_rate'], device)
    # plt.legend(np.arange(data.shape[0]))
    # plt.show()

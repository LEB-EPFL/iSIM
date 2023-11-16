import numpy as np
from functools import reduce
import operator
from typing import Dict, Any

class iSIMSettings(dict):
    """Central dict that holds all data necessary to run the iSIM.

    Different components can request views into the dict that are necessary for them to function.
    It includes information for the NIDAQ, pymmcore-plus etc.
    """
    def __init__(
        self,
        laser_powers: dict = {'488': 15, '561': 80, 'led': 50},
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
        ni_sample_rate: int = 60_066,
        full_settings: dict = None,
                 ):
        super().__init__()
        if full_settings is None:
            self['use_filters'] = use_filters
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

            self['save'] = True
            self['path'] = "C:/Users/stepp/Desktop/MyTIFF.ome.tiff"

            self['ni'] = {}
            self['ni']['twitchers'] = twitchers
            self['ni']['relative_z'] = relative_z
            self['ni']['laser_powers'] = laser_powers
            self['ni']['sample_rate'] = ni_sample_rate

            self['live'] = {"channel": "561", "fps": 5, "twitchers": False}
            self['live']['ni'] = {"laser_powers": {'488': 50, '561': 50, 'led': 100}}

            self['live_mode'] = False
        else:
            self.update(full_settings)

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
        self['exposure_time'] = self['acquisition']['channels'][0]['exposure']/1000
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
        if items:
            self.get_by_path(items[:-1])[items[-1]] = value
        else:
            self.update(value)


if __name__ == "__main__":
    from isim_control.ni.devices import NIDeviceGroup, main
    from isim_control.settings_translate import useq_from_settings, add_settings_from_core
    from pymmcore_plus import CMMCorePlus
    from pymmcore_widgets import ImagePreview
    import time
    from isim_control.ni.acquisition import AcquisitionEngine
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration("C:/iSIM/iSIM/mm-configs/pymmcore_plus.cfg")
    print(mmc.getCameraDevice())
    mmc.setCameraDevice("PrimeB_Camera")
    mmc.setProperty("PrimeB_Camera", "TriggerMode", "Edge Trigger")
    mmc.setProperty("PrimeB_Camera", "ReadoutRate", "100MHz 16bit")
    mmc.setProperty("Sapphire", "State", 1)
    mmc.setProperty("Quantum_561nm", "Laser Operation", "On")
    mmc.setAutoShutter(False)
    time.sleep(1)

    from qtpy.QtWidgets import QApplication
    app = QApplication([])
    preview = ImagePreview(mmcore=mmc)
    mmc.mda.events.frameReady.connect(preview._on_image_snapped)
    preview.show()

    acq = iSIMSettings(
        time_plan = {"interval": 0, "loops": 20}
        )
    acq['ni']['twitchers'] = True
    acq['ni']['relative_z'] = 129.34 # um
    # acq["acquisition"]["z_plan"] = {'range': 10, 'step': 2, }
    acq["acquisition"]["channels"] = ({'config': "561", 'exposure': 100}, )
    acq = add_settings_from_core(mmc, acq)
    acq.calculate_ni_settings()

    devices = NIDeviceGroup(acq)
    seq = useq_from_settings(acq)

    EXPOSURE = (acq['exposure_time'] + acq['camera']['readout_time'])*1000
    mmc.setExposure(EXPOSURE)
    print("Effective camera exposure", mmc.getExposure())

    engine = AcquisitionEngine(mmc, devices, acq)
    print(engine.task.timing.samp_clk_rate)
    print(acq['ni']['total_points'] + acq['ni']['readout_points']//3*2)
    mmc.mda.set_engine(engine)

    time.sleep(2)
    mmc.run_mda(seq)
    app.exec_()


    # import matplotlib.pyplot as plt
    # data = devices.get_data(next(seq.iter_events()))
    # for device in data:
    #     plt.step(np.arange(len(device))/acq['ni']['sample_rate'], device)
    #     # plt.plot(device)
    # plt.legend(np.arange(data.shape[0]))
    # plt.show()

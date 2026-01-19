from dataclasses import dataclass
from hardware._devices import DAQSettings


@dataclass
class NIDAQSettings(DAQSettings):
    sampling_rate: int = 4000
    post_delay: float = 0.0
    pre_delay: float = 0.0
    sweeps_per_frame: int = 1
    cycle_time: int = 100  # ms
    camera_readout_time: int = 0.029 # s

    def __post_init__(self):
        self.frame_rate = 1/(self.cycle_time*self.sweeps_per_frame/1000)
        self.final_sample_rate = round(self.sampling_rate*self.frame_rate*self.sweeps_per_frame**2)
        self.n_points = self.sampling_rate * self.sweeps_per_frame

    def new_acquisition_settings(self, cycle_time, camera_readout_time):
        self.cycle_time = cycle_time
        self.camera_readout_time = camera_readout_time
        self.__post_init__()
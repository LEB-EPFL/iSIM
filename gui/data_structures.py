from dataclasses import dataclass, field
import numpy as np
from typing import List, Any
from pathlib import Path


@dataclass
class PyImage:
    raw_image: np.ndarray
    timepoint: int
    channel: int
    z_slice: int
    time: int


@dataclass
class MMChannel:
    name: str
    active: bool
    power: float
    exposure_ms: int

@dataclass
class MMSettings:
    java_settings: Any = None

    timepoints: int =  11
    interval_ms: int = 1000

    pre_delay: float = 0.00
    post_delay: float = 0.03

    acq_order_mode: int = 0

    java_channels: Any = None
    channel_group: str = None
    use_channels: bool = True
    channels: List[MMChannel] = None
    n_channels: int = 0

    slices_start: float = None
    slices_end: float = None
    slices_step: float = None
    slices: List[float] = None
    use_slices: bool = False

    save_path: Path = None
    prefix: str = None

    sweeps_per_frame: int = 1

    acq_order: str = None


    def __post_init__(self):

        if self.java_settings is not None:
            # print(dir(self.java_settings))
            self.interval_ms = self.java_settings.interval_ms()
            self.timepoints = self.java_settings.num_frames()
            self.java_channels = self.java_settings.channels()
            self.acq_order = self.java_settings.acq_order_mode()
            self.use_channels = self.java_settings.use_channels()
            self.channel_group = self.java_settings.channel_group()
            if all([self.channel_group.lower() == "emission filter",
                    self.use_channels]):
                self.post_delay = 0.5
            self.acq_order_mode= self.java_settings.acq_order_mode()


        try:
            self.java_channels.size()
        except:
            return

        self.channels = {}
        self.n_channels = 0
        for channel_ind in range(self.java_channels.size()):
            channel = self.java_channels.get(channel_ind)
            config = channel.config()
            self.channels[config] = {'name': config,
                                     'use': channel.use_channel(),
                                     'exposure': channel.exposure(),
                                     'z_stack': channel.do_z_stack(),
                                     }
            if self.channels[config]['use']:
                self.n_channels += 1

        self.use_slices = self.java_settings.use_slices()
        self.java_slices = self.java_settings.slices()
        self.slices = []
        for slice_num in range(self.java_settings.slices().size()):
            self.slices.append(self.java_slices.get(slice_num))
        if len(self.slices) == 0:
            self.slices = [0]
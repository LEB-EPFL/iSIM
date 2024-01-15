from matplotlib import pyplot as plt
from typing import Protocol
import numpy as np
from scipy import ndimage
import useq
import nidaqmx

class DAQDevice(Protocol):
    """A device that can be controlled with data from an NIDAQ card."""

    def set_daq_settings(self, settings: dict) -> None:
        """Set sampling_rate and cycle time."""

    def one_frame(self, settings: dict) -> np.ndarray:
        """Return one frame that fits to the settings passed in."""

    def plot(self):
        """Plot the daq_data for one frame with matplotlib."""
        daq_data = self.one_frame(self.settings)
        x = np.divide(list(range(daq_data.shape[1])),self.settings.final_sample_rate/1000)
        for channel in range(daq_data.shape[0]):
            plt.step(x, daq_data[channel,:])


class NIDeviceGroup():
    def __init__(self, settings: dict = None):
        self.galvo = Galvo()
        self.camera = Camera()
        self.aotf = AOTF()
        self.twitcher = Twitcher()
        self.stage = Stage()
        self.led = LED()
        self.settings = settings or {}
        self.task, self.stream = self.make_task(settings)

    def get_data(self, event: useq.MDAEvent, next_event: useq.MDAEvent|None = None, live=False):
        galvo = self.galvo.one_frame(self.settings['ni'])[:-self.settings['ni']['readout_points']//3]
        stage = self.stage.one_frame(self.settings['ni'], event, next_event)[:-self.settings['ni']['readout_points']//3]
        camera = self.camera.one_frame(self.settings['ni'])[:-self.settings['ni']['readout_points']//3]
        aotf = self.aotf.one_frame(self.settings, event, live)[:, :-self.settings['ni']['readout_points']//3]
        led = self.led.one_frame(self.settings, event, live)[:, :-self.settings['ni']['readout_points']//3]
        twitchers = self.settings['ni']['twitchers'] if not live else self.settings['live']['twitchers']
        if twitchers:
            twitcher = self.twitcher.one_frame(self.settings['ni'])[:-self.settings['ni']['readout_points']//3]
        else:
            twitcher = np.ones(galvo.shape)*5
        # led[0, -1:] = np.ones(1)*6
        return np.vstack([galvo, stage, camera, aotf, led, twitcher])

    def make_task(self, settings):
        task = nidaqmx.Task()
        task.ao_channels.add_ao_voltage_chan('Dev1/ao0') # galvo channel
        task.ao_channels.add_ao_voltage_chan('Dev1/ao1') # z stage
        task.ao_channels.add_ao_voltage_chan('Dev1/ao2') # camera
        task.ao_channels.add_ao_voltage_chan('Dev1/ao3') # aotf blanking channel
        task.ao_channels.add_ao_voltage_chan('Dev1/ao4') # aotf 488 channel
        task.ao_channels.add_ao_voltage_chan('Dev1/ao5') # aotf 561 channel
        task.ao_channels.add_ao_voltage_chan('Dev1/ao6') # LED channel
        task.ao_channels.add_ao_voltage_chan('Dev1/ao7') # twitcher channel
        task.timing.cfg_samp_clk_timing(rate=self.settings['ni']['sample_rate'],
                                             samps_per_chan=settings['ni']['total_points'] +
                                             settings['ni']['readout_points']//3*2,)
        task.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.DONT_ALLOW_REGENERATION
        stream = nidaqmx.stream_writers.AnalogMultiChannelWriter(task.out_stream,
                                                                      auto_start=False)
        return task, stream

    def update_settings(self, settings: dict):
        self.settings = settings
        self.update_task(settings)

    def update_task(self, settings):
        self.task.timing.cfg_samp_clk_timing(rate=self.settings['ni']['sample_rate'],
                                samps_per_chan=settings['ni']['total_points'] +
                                settings['ni']['readout_points']//3*2,)


def makePulse(start, end, offset, n_points):
    duty_cycle = 10/n_points
    up = np.ones(round(duty_cycle*n_points))*start
    down = np.ones(n_points-round(duty_cycle*n_points))*end
    pulse = np.concatenate((up,down)) + offset
    return pulse


class Galvo(DAQDevice):
    """Galvo mirror, here for iSIM scanning"""
    def __init__(self):
        self.offset = -0.075  # -0.15
        self.amp = 0.2346  # 0.2346

    def one_frame(self, settings: dict) -> np.ndarray:
        #TODO: Sweeps per frame not possible anymore!
        readout_length = settings['readout_points']
        n_points = settings['exposure_points']

        galvo_frame = np.linspace(-self.amp, self.amp, n_points)
        overshoot_points = int(np.ceil(round(readout_length/20)/2))
        scan_increment = galvo_frame[-1] - galvo_frame[-2]
        self.overshoot_amp =  scan_increment * (overshoot_points + 1)
        overshoot_0 = np.linspace(-self.amp - self.overshoot_amp, -self.amp - scan_increment,
                                  overshoot_points)
        overshoot_1 = np.linspace(self.amp + scan_increment, self.amp + self.overshoot_amp,
                                  overshoot_points)
        galvo_frame = np.hstack((overshoot_0, galvo_frame, overshoot_1)) + self.offset
        galvo_frame = self.add_readout(galvo_frame, readout_length)
        return galvo_frame

    def add_readout(self, frame, readout_length):
        readout_length = readout_length - int(np.ceil(round(readout_length/20)/2))
        readout_delay0 = np.linspace(self.offset, -self.amp+self.offset-self.overshoot_amp,
                                     int(np.floor(readout_length*0.9)))
        readout_delay0 = np.hstack([readout_delay0,
                                    np.ones(int(np.ceil(readout_length*0.1)))*readout_delay0[-1]])
        readout_delay1 = np.linspace(self.offset + self.amp + self.overshoot_amp, self.offset,
                                     int(np.floor(readout_length*0.5)))
        readout_delay11 = np.ones(int(np.ceil(readout_length*0.5)))*self.offset
        return np.hstack([readout_delay0, frame, readout_delay1, readout_delay11])


class Camera(DAQDevice):
        def __init__(self):
            self.pulse_voltage = 5

        def one_frame(self, settings: dict) -> np.ndarray:
            camera_frame = makePulse(self.pulse_voltage, 0, 0, settings['exposure_points'])
            camera_frame = self.add_readout(camera_frame, settings['readout_points'])
            return camera_frame

        def add_readout(self, frame, readout_points):
            readout_delay = np.zeros(readout_points)
            return np.hstack([frame, readout_delay, readout_delay])


class Twitcher(DAQDevice):
    def __init__(self):
        self.amp = 0.07
        # The sampling rate in the settings should divide nicely with the frequency
        # self.freq = 2400  # Full cycle Hz
        self.n_waves = 240
        self.offset = 5

    def one_frame(self, settings: dict) -> np.ndarray:
        # wavelength = 1/self.freq*settings["sample_rate"]  # seconds
        # n_waves = (settings['exposure_points'])/wavelength

        points_per_wave = int(np.ceil(settings['exposure_points']/self.n_waves))
        print(points_per_wave)
        up = np.linspace(-1, 1, points_per_wave//2 + 1)
        down = np.linspace(1, -1, points_per_wave//2 + 1)
        start = np.linspace(0, -1, points_per_wave//4 + 1)
        end = np.linspace(-1, 0, points_per_wave//4 + 1)
        frame = np.hstack((start[:-1], np.tile(np.hstack((up[:-1], down[:-1])),
                                               round(self.n_waves + 20)), end))
        missing_points = settings['total_points'] + settings['readout_points'] - frame.shape[0]
        frame = np.hstack([np.ones(int(np.floor(missing_points/2)))*frame[0],
                           frame,
                           np.ones(int(np.ceil(missing_points/2)))*frame[-1]])

        frame = ndimage.gaussian_filter1d(frame, points_per_wave/20)
        frame = frame*(self.amp/frame.max()) + self.offset
        return frame


class AOTF(DAQDevice):
    def __init__(self):
        self.blank_voltage = 10

    def one_frame(self, settings: dict, event:useq.MDAEvent, live=False) -> np.ndarray:
        if live:
            laser_powers = settings['live']['ni']['laser_powers']
        else:
            laser_powers = settings['ni']['laser_powers']
            # settings['ni']['laser_powers'] = settings['live']['ni']['laser_powers']
        settings = settings['ni']
        n_points = settings['exposure_points']

        blank = np.ones(n_points) * self.blank_voltage
        if event.channel.config == '488':
            aotf_488 = np.ones(n_points) * laser_powers['488']/10
            aotf_561 = np.zeros(n_points)
        elif event.channel.config == '561':
            aotf_488 = np.zeros(n_points)
            aotf_561 = np.ones(n_points) * laser_powers['561']/10
        else:
            aotf_488 = np.zeros(n_points)
            aotf_561 = np.zeros(n_points)
            blank = np.zeros(n_points)
        aotf = np.vstack((blank, aotf_488, aotf_561))
        aotf = self.add_readout(aotf, settings['readout_points'])
        return aotf

    def add_readout(self, frame: np.ndarray, readout_points: int) -> np.ndarray:
        readout_delay = np.zeros((frame.shape[0], readout_points))
        frame = np.hstack([readout_delay, frame,  readout_delay])
        return frame


class Stage(DAQDevice):
    def __init__(self):
        self.pulse_voltage = 5
        self.calibration = 202.161
        self.max_v = 10

    def one_frame(self, settings: dict, event: useq.MDAEvent,
                  next_event: useq.MDAEvent|None = None) -> np.ndarray:
        # relative_z = settings['relative_z']
        # height_offset = relative_z if event.z_pos is None else (event.z_pos + relative_z)
        height_offset = 0 if event.z_pos is None else event.z_pos
        height_offset = self.convert_z(height_offset)
        stage_frame = (np.ones(settings['readout_points'] + settings['exposure_points']) *
                       height_offset)
        stage_frame = self.add_readout(stage_frame, settings['readout_points'], next_event)
        return stage_frame

    def convert_z(self, z_um):
        return (z_um/self.calibration) * self.max_v

    def add_readout(self, frame, readout_points, next_event:useq.MDAEvent|None):
        if next_event is None or next_event.z_pos is None:
            height_offset = frame[-1]
        else:
            height_offset = next_event.z_pos
        readout_delay = np.ones(readout_points)*self.convert_z(height_offset)
        frame = np.hstack([frame, readout_delay])
        return frame


class LED(DAQDevice):
    def __init__(self):
        self.power = 5
        self.speed_adjustment = 1.002
        self.low_power_adj = {0: 1, 1: 1, 2: 1, 3: 0.86, 4: 0.95, 5: 0.97, 6: 0.978}

    def one_frame(self, settings: dict, event:useq.MDAEvent, live=False) -> np.ndarray:
        if live:
            power = settings['live']['ni']['laser_powers']['led']
        else:
            power = settings['ni']['laser_powers']['led']
        #Adjust the timing if power is low, otherwise black bars in image
        if power < 7:
            speed_adjust = self.low_power_adj[power]
        elif power < 20:
            speed_adjust = self.speed_adjustment - ((20 - power) / 800)
        else:
            speed_adjust = 1.002
        settings = settings['ni']
        if event.channel.config.lower() != 'led':
            return np.expand_dims(np.zeros(settings['total_points'] +
                                           settings['readout_points']), 0)
        self.adjusted_readout = (settings['readout_points'] / settings['sample_rate']
                                 * speed_adjust)
        n_points = (settings['total_points'] -
                    round(self.adjusted_readout * settings['sample_rate']))
        led = np.ones(n_points) * power/10
        led = np.expand_dims(led, 0)
        led = self.add_readout(led, settings)
        return led

    def add_readout(self, frame:np.ndarray, settings: dict) -> np.ndarray:
        n_shift = (round(settings['readout_points']) -
                   round(settings['sample_rate'] * self.adjusted_readout))
        readout_delay0 = np.zeros((frame.shape[0], settings['readout_points'] - n_shift))
        readout_delay1 = np.zeros((frame.shape[0], settings["readout_points"]))
        frame = np.hstack([readout_delay0, frame, readout_delay1])
        return frame


def main(settings: dict = None, data: np.ndarray = None):
    if data is None:
        from isim_control.settings import iSIMSettings
        from isim_control.settings_translate import useq_from_settings
        if not settings:
            settings = iSIMSettings()
            settings['ni']['twitchers'] = True
        devices = NIDeviceGroup(settings)
        seq = useq_from_settings(settings)

        data = devices.get_data(next(seq.iter_events()))
    import matplotlib.pyplot as plt
    for device in data:
        plt.step(np.arange(len(device))/settings['ni']['sample_rate'], device)
    plt.legend(np.arange(data.shape[0]))
    plt.show()

if __name__ == "__main__":
    main()
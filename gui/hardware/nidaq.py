from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from MicroManagerControl import MicroManagerControl
import nidaqmx
import nidaqmx.stream_writers
import numpy as np
import copy

from scipy import ndimage
import matplotlib.pyplot as plt

import time
from pymm_eventserver.data_structures import MMSettings
from pymm_eventserver.event_thread import EventListener
from gui.GUIWidgets import SettingsView
from hardware.FilterFlipper import Flippers
from alignment import NI
from hardware.nidaq_components.settings import NIDAQSettings
from isimgui.hardware.nidaq_components.devices import Galvo, Camera, Twitcher, LED, AOTF, Stage

class NIDAQ(QObject):

    new_ni_settings = pyqtSignal(MMSettings)

    def __init__(self, event_thread: EventListener, mm_interface: MicroManagerControl):
        super().__init__()
        self.event_thread = event_thread
        self.core = self.event_thread.core
        self.studio = self.event_thread.studio
        self.mm_interface = mm_interface

        #Get the EDA setting to only do things when EDA is off, otherwise the daq_actuator is active
        eda = self.core.get_property('EDA', "Label")
        self.eda = False if eda == "Off" else True

        settings = self.studio.acquisitions().get_acquisition_settings()
        self.settings = MMSettings(settings)

        self.system = nidaqmx.system.System.local()

        self.sampling_rate = 9600
        self.update_settings(self.settings)

        self.ni_settings = NIDAQSettings(self.sampling_rate)
        self.galvo = Galvo(self.ni_settings)
        self.stage = Stage(self.ni_settings)
        self.camera = Camera(self.ni_settings)
        self.aotf = AOTF(self.ni_settings)
        self.brightfield_control = Brightfield(self)
        self.led = LED(self.ni_settings)
        self.twitcher = Twitcher(self.ni_settings)

        self.acq = Acquisition(self, self.settings)
        self.live = LiveMode(self)

        self.task = None
        self.last_laser_channel = "488"

        self.acq.set_z_position.connect(self.mm_interface.set_z_position)

        self.event_thread.live_mode_event.connect(self.start_live)
        self.event_thread.configuration_settings_event.connect(self.power_settings)
        self.event_thread.configuration_settings_event.connect(self.live.channel_setting)

        self.event_thread.acquisition_started_event.connect(self.run_acquisition_task)
        self.event_thread.acquisition_ended_event.connect(self.acq_done)
        self.event_thread.mda_settings_event.connect(self.new_settings)


    def init_task(self):
        try: self.task.close()
        except: print("Task close failed")
        self.task = nidaqmx.Task()
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao0') # galvo channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao1') # z stage
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao2') # camera channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao3') # aotf blanking channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao4') # aotf 488 channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao5') # aotf 561 channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao6') # LED channel
        self.task.ao_channels.add_ao_voltage_chan('Dev1/ao7') # twitcher channel

    def update_settings(self, new_settings):
        try:
            self.cycle_time = new_settings.channels['488']['exposure']
        except KeyError:
            print("WARNING: Empty channels received, setting exposure time to 100 ms.")
            self.cycle_time = 100

        self.sweeps_per_frame = new_settings.sweeps_per_frame
        self.frame_rate = 1/(self.cycle_time*self.sweeps_per_frame/1000)
        self.smpl_rate = round(self.sampling_rate*self.frame_rate*self.sweeps_per_frame*self.sweeps_per_frame)
        self.n_points = self.sampling_rate*self.sweeps_per_frame
        #settings for all pulses:
        self.duty_cycle = 10/self.n_points
        self.settings = new_settings
        print('NI settings set')

    @pyqtSlot(MMSettings)
    def new_settings(self, new_settings: MMSettings):
        if len(new_settings.channels) == 0:
            print("WARNING: Empty channels dict! Not setting")
        else:
            self.settings = new_settings
            new_settings.post_delay = 0.03
            self.settings.post_delay = 0.03
        self.ni_settings.camera_readout_time = float(self.core.get_property("PrimeB_Camera",
                                                                      "Timing-ReadoutTimeNs"))*1E-9
        self.ni_settings.cycle_time = new_settings.channels['488']["exposure"]
        self.update_settings(new_settings)
        self.acq.update_settings(new_settings)
        self.live.update_settings(new_settings)
        print('NEW SETTINGS SET')

    @pyqtSlot(str, str, str)
    def power_settings(self, device, prop, value):
        print(device)
        if device == "488_AOTF" and prop == r"Power (% of max)":
            self.aotf.power_488 = float(value)
        elif device == "561_AOTF" and prop == r"Power (% of max)":
            self.aotf.power_561 = float(value)
        elif device == "exposure":
            self.settings.channels['488']['exposure'] = float(value)
            self.update_settings(self.settings)
        elif device == 'PrimeB_Camera' and prop == "TriggerMode":
            print(value)
            brightfield = True if value == "Internal Trigger" else False
            self.brightfield_control.toggle_flippers(brightfield)
        elif device == "DLightPath":
            if value == "iSIM":
                print("SETTING", self.last_laser_channel)
                self.core.set_property("DPseudoChannel", "Label", self.last_laser_channel)
                self.event_thread.studio.get_application().refresh_gui()
                self.live.channel_setting("DPseudoChannel", "Label", self.last_laser_channel)
        elif device == "twitcher":
            print("NEW twitcher settings")
            if prop == "amp":
                self.twitcher.amp = float(value)
            elif prop == "freq":
                self.twitcher.freq = int(value)
        elif device == "EDA" and prop == "Label":
            eda = self.core.get_property('EDA', "Label")
            self.eda = False if eda == "Off" else True
            # Close the task if EDA is going to take over
            if self.eda:
                try:
                    self.task.close()
                except AttributeError:
                    print("No task defined yet.")
                self.event_thread.acquisition_started_event.disconnect(self.run_acquisition_task)
                self.event_thread.acquisition_ended_event.disconnect(self.acq_done)
                self.event_thread.mda_settings_event.disconnect(self.new_settings)
            else:
                self.update_settings(self.settings)
                self.event_thread.acquisition_started_event.connect(self.run_acquisition_task)
                self.event_thread.acquisition_ended_event.connect(self.acq_done)
                self.event_thread.mda_settings_event.connect(self.new_settings)
        print(device, prop, value)
        if device in ["561_AOTF", "488_AOTF", 'exposure']:
            self.live.make_daq_data()

    @pyqtSlot(object)
    def run_acquisition_task(self, _):
        # print("Running acquisition task")
        # settings = MMSettings(java_settings=_.get_settings())
        if not self.eda:
            # self.adjust_exposure()
            try:
                self.event_thread.mda_settings_event.disconnect(self.new_settings)
            except TypeError:
                print("WARNING: mda_settings disconnect failed, did last acq end normal?")
            time.sleep(0.5)
            self.acq.run_acquisition()

    @pyqtSlot(object)
    def acq_done(self, _):
        # self.reset_exposure()
        self.event_thread.mda_settings_event.connect(self.new_settings)
        self.acq.set_z_position.emit(self.acq.orig_z_position)
        # self.event_thread.mda_settings_event.connect(self.new_settings)
        time.sleep(1)
        self.init_task()
        stop_data = np.asarray([[self.galvo.parking_voltage, 0, 0, 0, 0, 0, 0, 5]]).astype(np.float64).transpose()
        self.task.write(stop_data)

    @pyqtSlot(bool)
    def start_live(self, live_is_on):
        if live_is_on and not self.live.brightfield:
            self.last_laser_channel = self.core.get_property("DPseudoChannel", "Label")
            print("SAVED ", self.last_laser_channel)
            self.event_thread.mda_settings_event.disconnect(self.new_settings)
            # self.adjust_exposure()
        elif not live_is_on and not self.live.brightfield:
            # self.reset_exposure()
            self.event_thread.mda_settings_event.connect(self.new_settings)
        self.live.toggle(live_is_on)
        # print(self.core.get_property("PrimeB_Camera", "Exposure"))

    def generate_one_timepoint(self, live_channel: int = None, z_inverse: bool = False):
        if live_channel == "LED":
            timepoint = np.ndarray((6,1))
            return timepoint
        print("one timepoint post_delay", self.settings.post_delay)

        if not self.settings.use_channels or live_channel is not None:
            old_post_delay = self.settings.post_delay
            self.settings.post_delay = 0.03
            galvo = self.galvo.one_frame(self.ni_settings)
            channel_name = '488' if live_channel is None else live_channel
            stage = self.stage.one_frame(self.ni_settings, 0)
            aotf = self.aotf.one_frame(self.ni_settings, self.settings.channels[channel_name])
            camera = self.camera.one_frame(self.ni_settings)
            led = self.led.one_frame(self.ni_settings, 0)
            twitcher = self.twitcher.one_frame(self.ni_settings)
            timepoint = np.vstack((galvo, stage, camera, aotf, led, twitcher))
            self.settings.post_delay = old_post_delay
        else:
            galvo = self.galvo.one_frame(self.ni_settings)
            led = self.led.one_frame(self.ni_settings, 0)
            twitcher = self.twitcher.one_frame(self.ni_settings)
            camera = self.camera.one_frame(self.ni_settings)
            if self.settings.acq_order_mode == 1:
                timepoint = self.slices_then_channels(galvo, camera, led, twitcher)
            elif self.settings.acq_order_mode == 0:
                timepoint = self.channels_then_slices(galvo, camera, led, twitcher, z_inverse)
        print(timepoint.shape)
        return timepoint

    def get_slices(self):
        iter_slices = copy.deepcopy(self.settings.slices)
        iter_slices_rev = copy.deepcopy(iter_slices)
        iter_slices_rev.reverse()
        return iter_slices, iter_slices_rev

    def channels_then_slices(self, galvo, camera, led, twitcher, z_inverse):
        iter_slices, iter_slices_rev = self.get_slices()

        slices_data = []
        slices = iter_slices if not z_inverse else iter_slices_rev
        for sli in slices:
            channels_data = []
            for channel in self.settings.channels.values():
                if channel.get('use', False):
                    aotf = self.aotf.one_frame(self.ni_settings, channel)
                    offset = sli - self.settings.slices[0]
                    stage = self.stage.one_frame(self.ni_settings, offset)
                    data = np.vstack((galvo, stage, camera, aotf, led, twitcher))
                    channels_data.append(data)
            data = np.hstack(channels_data)
            slices_data.append(data)
        return np.hstack(slices_data)

    def slices_then_channels(self, galvo, camera, led, twitcher):
        iter_slices, iter_slices_rev = self.get_slices()
        z_iter = 0
        channels_data = []
        for channel in self.settings.channels.values():
            if channel['use']:
                slices_data = []
                slices = iter_slices if not np.mod(z_iter, 2) else iter_slices_rev
                for sli in slices:
                    aotf = self.aotf.one_frame(self.ni_settings, channel)
                    offset = sli - self.settings.slices[0]
                    stage = self.stage.one_frame(self.ni_settings, offset)
                    data = np.vstack((galvo, stage, camera, aotf, led, twitcher))
                    slices_data.append(data)
                z_iter += 1
                data = np.hstack(slices_data)
                channels_data.append(data)
        return np.hstack(channels_data)

    def adjust_exposure(self):
        readout_time = self.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
        readout_time = float(readout_time)*1E-6  # in milliseconds
        exposure_set = float(self.core.get_property("PrimeB_Camera", "Exposure"))
        self.core.set_property("PrimeB_Camera", "Exposure", exposure_set + readout_time)
        self.core.set_exposure(exposure_set + readout_time)
        # self.event_thread.bridge.get_studio().get_application().set_exposure(exposure_set + readout_time)
        print("Exposure set to ",  exposure_set + readout_time)

    def reset_exposure(self):
        self.core.set_property("PrimeB_Camera", "Exposure", self.cycle_time)
        self.core.set_exposure( self.cycle_time)

    def plot(self, all: bool = False):
        if not all:
            for device in self.generate_one_timepoint():
                plt.plot(device)
        else:
            for device in self.acq.daq_data:
                plt.plot(device)


class LiveMode(QObject):
    def __init__(self, ni:NIDAQ):
        super().__init__()
        self.ni = ni
        core = self.ni.core
        self.channel_name= core.get_property('DPseudoChannel', "Label")
        self.ready = self.make_daq_data()
        self.stop = False
        self.brightfield = core.get_property('DPseudoChannel', "Label")
        self.brightfield = (self.brightfield == "LED")
        self.ni.brightfield_control.flippers.brightfield(self.brightfield)

    @pyqtSlot(str, str, str)
    def channel_setting(self, device, prop, value):
        if device == "DPseudoChannel" and prop == "Label":
            self.channel_name = value
            self.make_daq_data()
        if device == "DPseudoChannel" and prop == "Label":
            self.brightfield = (value == "LED")


    def update_settings(self, new_settings):
        self.ni.init_task()
        self.ni.task.timing.cfg_samp_clk_timing(rate=self.ni.smpl_rate,
                                             sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
                                             samps_per_chan=self.daq_data.shape[1])
        self.ni.task.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.DONT_ALLOW_REGENERATION
        self.ni.stream = nidaqmx.stream_writers.AnalogMultiChannelWriter(self.ni.task.out_stream,
                                                                         auto_start=False)
        self.ni.stream.write_many_sample(self.daq_data)
        self.ni.task.register_every_n_samples_transferred_from_buffer_event(self.daq_data.shape[1]//2,
                                                                            self.get_new_data)

    def get_new_data(self, task_handle, every_n_samples_event_type, number_of_samples, callback_data):
        if self.stop:
            self.ni.task.stop()
            self.send_stop_data()
        else:
            self.ni.stream.write_many_sample(self.daq_data)
        return 0

    def make_daq_data(self):
        try:
            timepoint = self.ni.generate_one_timepoint(live_channel = self.channel_name)
        except KeyError:
            print("WARNING: are there channels in the MDA window?")
            return False
        no_frames = np.max([1, round(1000/self.ni.cycle_time)])
        print("N Frames ", no_frames)
        self.daq_data = np.tile(timepoint, no_frames)
        self.stop_data = np.asarray(
                [[self.ni.galvo.parking_voltage, 0, 0, 0, 0, 0, 0, 5]]).astype(np.float64).transpose()
        print(self.daq_data.shape[1])
        return True

    def send_stop_data(self):
        self.ni.init_task()
        self.ni.task.write(self.stop_data)

    def toggle(self, live_is_on):
        print(live_is_on)
        if self.brightfield:
            if live_is_on:
                # self.ni.brightfield_control.led(live_is_on, 0.3)
                core = self.ni.event_thread.core
                readout_time = core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
                readout_time = float(readout_time)*1E-9
                print(self.ni.settings.channels['488']["exposure"])
                self.brightfield_ni = NI(settings=NIDAQSettings(cycle_time = self.ni.settings.channels['488']["exposure"],
                sampling_rate = 9000, camera_readout_time=0.023))
                self.brightfield_ni.aotf.power_488 = 0
                self.brightfield_ni.galvo.amp = 0.233
                self.brightfield_ni.daq_data = self.brightfield_ni.one_sequence()
                self.brightfield_ni.start()
                return
            else:
                self.brightfield_ni.stop()
                time.sleep(1)
                self.brightfield_ni.cleanup()

        if live_is_on:
            if not self.ready:
                core = self.ni.event_thread.bridge.get_core()
                self.channel_name = core.get_property('DPseudoChannel', "Label")
                self.ready = self.make_daq_data()
            self.stop = False
            self.update_settings(self.ni.settings)
            self.ni.task.start()
            print("STARTED", time.perf_counter())
        else:
            self.stop = True

    def plot_trigger_data(self):
        for device in self.daq_data:
            plt.plot(device)
        plt.show()
        return True

class Acquisition(QObject):
    set_z_position = pyqtSignal(float)
    def __init__(self, ni:NIDAQ, settings: MMSettings):
        super().__init__()
        self.settings = settings
        self.ni = ni
        self.daq_data = None
        self.ready = self.make_daq_data()
        self.orig_z_position = None

    def update_settings(self, new_settings):
        self.ready = False
        #TODO: Check what is actually going on here if empty channels come in
        if len(new_settings.channels) == 0:
            print("WARNING: empty channels dict!")
        else:
            self.settings = new_settings
        self.make_daq_data()
        self.ni.init_task()
        self.ni.task.timing.cfg_samp_clk_timing(rate=self.ni.smpl_rate,
                                sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                samps_per_chan=self.daq_data.shape[1])
        self.ni.stream = nidaqmx.stream_writers.AnalogMultiChannelWriter(self.ni.task.out_stream,
                                                                         auto_start=False)
        print('Stream length ', self.daq_data.shape[1])
        self.ready = True

    def make_daq_data(self):
        try:
            timepoint = self.ni.generate_one_timepoint()
        except ValueError as e:
            print("WARNING: Are the channels in the MDA pannel?")
            print(e)
            return False
        timepoint = self.add_interval(timepoint)
        # Make zstage go up/down over two timepoints
        if self.settings.acq_order_mode == 0:
            timepoint_inverse = self.ni.generate_one_timepoint(z_inverse=True)
            timepoint_inverse = self.add_interval(timepoint_inverse)
            double_timepoint = np.hstack([timepoint, timepoint_inverse])
            self.daq_data = np.tile(double_timepoint, int(np.floor(self.settings.timepoints/2)))
            if self.settings.timepoints % 2 == 1:
                self.daq_data = np.hstack([self.daq_data, timepoint])
        else:
            self.daq_data = np.tile(timepoint, self.settings.timepoints)
        return True

    def add_interval(self, timepoint):
        if (self.ni.smpl_rate*self.settings.interval_ms/1000 <= timepoint.shape[1] and
            self.settings.interval_ms > 0):
            print('Error: interval time shorter than time required to acquire single timepoint.')
            self.settings.interval_ms = 0

        if self.settings.interval_ms > 0:
            missing_samples = round(self.ni.smpl_rate * self.settings.interval_ms/1000-timepoint.shape[1])
            galvo = np.ones(missing_samples) * self.ni.galvo.parking_voltage
            last_data = np.expand_dims(timepoint[1:,-1], 1)
            rest = np.tile(last_data, missing_samples)  # np.zeros((timepoint.shape[0] - 1, missing_samples))
            delay = np.vstack([galvo, rest])
            timepoint = np.hstack([timepoint, delay])
        print("INTERVAL: ", self.settings.interval_ms)
        return timepoint

    def run_acquisition(self, settings=None):
        if settings is None:
            self.update_settings(self.settings)
            my_settings = self.settings
        else:
            print("Using directly transmitted settings")
            self.update_settings(settings)
            my_settings = settings
        self.orig_z_position = self.ni.core.get_position()
        if my_settings.use_slices:
            self.set_z_position.emit(self.settings.slices[0])
            time.sleep(0.1)
        time.sleep(0.5)
        print("WRITING, ", self.daq_data.shape)
        written = self.ni.stream.write_many_sample(self.daq_data, timeout=20)
        # time.sleep(0.5)
        self.ni.task.start()
        print('================== Data written        ', written)

    def adjust_exposure(self):
        readout_time = self.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
        readout_time = float(readout_time)*1E-6  # in milliseconds
        exposure_set = float(self.core.get_property("PrimeB_Camera", "Exposure"))
        self.core.set_property("PrimeB_Camera", "Exposure", exposure_set + readout_time)
        self.core.set_exposure(exposure_set + readout_time)
        print("Exposure set to ",  exposure_set + readout_time)

    def reset_exposure(self):
        self.core.set_property("PrimeB_Camera", "Exposure", self.exposure)
        self.core.set_exposure(self.exposure)


def make_pulse(ni, start, end, offset):
    up = np.ones(round(ni.duty_cycle*ni.n_points))*start
    down = np.ones(ni.n_points-round(ni.duty_cycle*ni.n_points))*end
    pulse = np.concatenate((up,down)) + offset
    return pulse


# class Galvo:
#     def __init__(self, ni: NIDAQ):
#         self.ni = ni
#         self.offset = -0.075  # -0.15
#         self.amp = 0.2346  # 0.234
#         self.parking_voltage = self.offset  # -3.2

#     def one_frame(self, settings):
#         #TODO: Sweeps per frame not possible anymore!
#         self.n_points = self.ni.sampling_rate*settings.sweeps_per_frame
#         self.readout_time = self.ni.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         self.readout_time = float(self.readout_time)*1E-9  # in seconds
#         # down1 = np.linspace(0,-self.amp_0,round(self.n_points/(4*settings.sweeps_per_frame)))
#         # up = np.linspace(-self.amp_0,self.amp_0,round(self.n_points/(2*settings.sweeps_per_frame)))
#         # down2 = np.linspace(self.amp_0,0,round(self.n_points/settings.sweeps_per_frame) -
#         #                     round(self.n_points/(4*settings.sweeps_per_frame)) -
#         #                     round(self.n_points/(2*settings.sweeps_per_frame)))
#         # galvo_frame = np.concatenate((down1, up, down2))
#         # galvo_frame = np.tile(galvo_frame, settings.sweeps_per_frame)
#         # galvo_frame = galvo_frame[0:self.n_points]
#         # Make this 30 ms shorter for the camera readout
#         """This is before twitcher"""
#         # n_points = self.n_points - round(readout_time * self.ni.smpl_rate)
#         # galvo_frame = np.linspace(-self.amp_0, self.amp_0, n_points) + self.offset_0
#         # # Add the 10 ms in the waiting position
#         # readout_delay0 = np.ones(round(self.ni.smpl_rate * readout_time)) * (-self.amp_0 + self.offset_0)
#         # readout_delay1 = np.ones(round(self.ni.smpl_rate * readout_time)) * (self.amp_0 + self.offset_0)
#         # galvo_frame = np.hstack([readout_delay0, galvo_frame, readout_delay1])
#         readout_length = round(self.readout_time * self.ni.smpl_rate)
#         n_points = self.n_points - readout_length
#         galvo_frame = np.linspace(-self.amp, self.amp, n_points)
#         # Make sure the galvo is already moving when the laser comes on.
#         overshoot_points = int(np.ceil(round(readout_length/20)/2))
#         scan_increment = galvo_frame[-1] - galvo_frame[-2]
#         self.overshoot_amp =  scan_increment * (overshoot_points + 1)
#         overshoot_0 = np.linspace(-self.amp - self.overshoot_amp, -self.amp - scan_increment, overshoot_points)
#         overshoot_1 = np.linspace(self.amp + scan_increment, self.amp + self.overshoot_amp, overshoot_points)
#         galvo_frame = np.hstack((overshoot_0, galvo_frame, overshoot_1)) + self.offset
#         galvo_frame = self.add_readout(galvo_frame)
#         galvo_frame = self.add_delays(galvo_frame, settings)
#         return galvo_frame
#         # galvo_frame = self.add_delays(galvo_frame, settings)
#         # return galvo_frame

#     def add_readout(self, frame):
#         readout_length = round(self.ni.smpl_rate * self.readout_time)
#         readout_length = readout_length - int(np.ceil(round(readout_length/20)/2))  # round(readout_length/20/2)
#         readout_delay0 = np.linspace(self.offset, -self.amp+self.offset-self.overshoot_amp, int(np.floor(readout_length*0.9)))
#         readout_delay0 = np.hstack([readout_delay0, np.ones(int(np.ceil(readout_length*0.1)))*readout_delay0[-1]])
#         readout_delay1 = np.linspace(self.offset + self.amp + self.overshoot_amp, self.offset, readout_length)
#         return np.hstack([readout_delay0, frame, readout_delay1])

#     def add_delays(self, frame, settings):
#         # settings.post_delay = 0
#         if settings.post_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.post_delay)) * self.parking_voltage
#             frame = np.hstack([frame, delay])
#         if settings.pre_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.pre_delay)) * self.parking_voltage
#             frame = np.hstack([delay, frame])
#         return frame

# class Twitcher0:
#     """Here just to output solid 5V for now"""
#     def __init__(self, ni: NIDAQ):
#         self.ni = ni

#     def one_frame(self, settings):
#         self.n_points = self.ni.sampling_rate*settings.sweeps_per_frame
#         frame = np.ones(self.n_points) * 5
#         frame = self.add_readout(frame)
#         frame = self.add_delays(frame, settings)
#         return frame

#     def add_readout(self, frame):
#         readout_time = self.ni.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         readout_time = float(readout_time)*1E-9  # in seconds
#         readout_delay = np.ones(round(self.ni.smpl_rate * readout_time))* frame[-1]
#         frame = np.hstack([frame, readout_delay])
#         return frame

#     def add_delays(self, frame, settings):
#         if settings.post_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.post_delay))* frame[-1]
#             frame = np.hstack([frame, delay])

#         if settings.pre_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.pre_delay))* frame[-1]
#             frame = np.hstack([delay, frame])

#         return frame


# class Twitcher:
#     def __init__(self, ni:NIDAQ):
#         self.ni = ni
#         self.amp = 0.05
#         # The sampling rate in the settings should divide nicely with the frequency
#         self.freq = 2400  # Full cycle Hz
#         self.offset = 5

#     def one_frame(self, settings) -> np.ndarray:
#         self.n_points = self.ni.sampling_rate*settings.sweeps_per_frame
#         readout_time = self.ni.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         readout_time = float(readout_time)*1E-9  # in seconds
#         n_points = self.n_points + round(readout_time * self.ni.smpl_rate)
#         frame_time = n_points/self.ni.smpl_rate + readout_time # seconds
#         wavelength = 1/self.freq  # seconds
#         n_waves = frame_time/wavelength
#         points_per_wave = int(np.ceil(n_points/n_waves))
#         up = np.linspace(-1, 1, points_per_wave//2 + 1)
#         down = np.linspace(1, -1, points_per_wave//2 + 1)
#         frame = np.hstack((down[:-1], np.tile(np.hstack((up[:-1], down[:-1])), round(n_waves + 20)), up[:-1]))
#         frame = ndimage.gaussian_filter1d(frame, points_per_wave/20)
#         frame = frame[points_per_wave//2:n_points + points_per_wave//2]
#         frame = frame*(self.amp/frame.max()) + self.offset
#         frame = self.add_delays(frame, settings)
#         frame = np.expand_dims(frame, 0)
#         return frame


#     def add_delays(self, frame, settings):
#         if settings.post_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.post_delay))* frame[-1]
#             frame = np.hstack([frame, delay])

#         if settings.pre_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.pre_delay))* frame[0]
#             frame = np.hstack([delay, frame])

#         return frame

# class LED:
#     """Here just to output solid 5V for now"""
#     def __init__(self, ni: NIDAQ):
#         self.ni = ni

#     def one_frame(self, settings):
#         self.n_points = self.ni.sampling_rate*settings.sweeps_per_frame
#         frame = np.ones(self.n_points) * 0
#         frame = self.add_readout(frame)
#         frame = self.add_delays(frame, settings)
#         return frame

#     def add_readout(self, frame):
#         readout_time = self.ni.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         readout_time = float(readout_time)*1E-9  # in seconds
#         readout_delay = np.ones(round(self.ni.smpl_rate * readout_time))* frame[-1]
#         frame = np.hstack([frame, readout_delay])
#         return frame

#     def add_delays(self, frame, settings):
#         if settings.post_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.post_delay))* frame[-1]
#             frame = np.hstack([frame, delay])

#         if settings.pre_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.pre_delay))* frame[-1]
#             frame = np.hstack([delay, frame])

#         return frame

# class Stage:
#     def __init__(self, ni: NIDAQ):
#         self.ni = ni
#         self.pulse_voltage = 5
#         self.calibration = 202.161
#         self.max_v = 10

#     def one_frame(self, settings, height_offset):
#         height_offset = self.convert_z(height_offset)
#         stage_frame = make_pulse(self.ni, height_offset, height_offset, 0)
#         stage_frame = self.add_readout(stage_frame)
#         stage_frame = self.add_delays(stage_frame, settings)
#         return stage_frame

#     def convert_z(self, z_um):
#         return (z_um/self.calibration) * self.max_v

#     def add_readout(self, frame):
#         readout_time = self.ni.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         readout_time = float(readout_time)*1E-9  # in seconds
#         readout_delay = np.ones(round(self.ni.smpl_rate * readout_time))* frame[-1]
#         frame = np.hstack([frame, readout_delay])
#         return frame

#     def add_delays(self, frame, settings):
#         if settings.post_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.post_delay))* frame[-1]
#             frame = np.hstack([frame, delay])

#         if settings.pre_delay > 0:
#             delay = np.ones(round(self.ni.smpl_rate * settings.pre_delay))* frame[-1]
#             frame = np.hstack([delay, frame])

#         return frame


# class Camera:
#     def __init__(self, ni: NIDAQ):
#         self.ni = ni
#         self.pulse_voltage = 5

#     def one_frame(self, settings):
#         camera_frame = make_pulse(self.ni, self.pulse_voltage, 0, 0)
#         camera_frame = self.add_readout(camera_frame)
#         camera_frame = self.add_delays(camera_frame, settings)
#         return camera_frame

#     def add_readout(self, frame):
#         readout_time = self.ni.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         readout_time = float(readout_time)*1E-9  # in seconds
#         readout_delay = np.zeros(round(self.ni.smpl_rate * readout_time))
#         frame = np.hstack([frame, readout_delay])
#         return frame

#     def add_delays(self, frame, settings):
#         if settings.post_delay > 0:
#             delay = np.zeros(round(self.ni.smpl_rate * settings.post_delay))
#             frame = np.hstack([frame, delay])

#         if settings.pre_delay > 0:
#             delay= np.zeros(round(self.ni.smpl_rate * settings.pre_delay))
#             frame = np.hstack([delay, frame])
#         return frame


# class AOTF:
#     def __init__(self, ni:NIDAQ):
#         self.ni = ni
#         self.blank_voltage = 10
#         core = self.ni.core
#         self.power_488 = float(core.get_property('488_AOTF',r"Power (% of max)"))
#         self.power_561 = float(core.get_property('561_AOTF',r"Power (% of max)"))

#     def one_frame(self, settings:MMSettings, channel:dict):
#         self.n_points = self.ni.sampling_rate*settings.sweeps_per_frame
#         readout_time = self.ni.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         readout_time = float(readout_time)*1E-9  # in seconds
#         n_points = self.n_points - round(readout_time * self.ni.smpl_rate)

#         blank = np.ones(n_points) * self.blank_voltage
#         if channel['name'] == '488':
#             aotf_488 = np.ones(n_points) * self.power_488/10
#             aotf_561 = np.zeros(n_points)
#         elif channel['name'] == '561':
#             aotf_488 = np.zeros(n_points)
#             aotf_561 = np.ones(n_points) * self.power_561/10
#         elif channel['name'] == 'LED':
#             aotf_488 = np.zeros(n_points)
#             aotf_561 = np.zeros(n_points)
#         aotf = np.vstack((blank, aotf_488, aotf_561))
#         # aotf = np.hstack([np.zeros((3, 20)), aotf[:, 20:-20], np.zeros((3, 20))])
#         aotf = self.add_readout(aotf)
#         aotf = self.add_delays(aotf, settings)
#         return aotf

#     def add_readout(self, frame):
#         readout_time = self.ni.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         readout_time = float(readout_time)*1E-9  # in seconds
#         readout_delay = np.zeros((frame.shape[0], round(self.ni.smpl_rate * readout_time)))
#         frame = np.hstack([readout_delay, frame, readout_delay])
#         return frame


#     def add_delays(self, frame:np.ndarray, settings: MMSettings):
#         if settings.post_delay > 0:
#             delay = np.zeros((frame.shape[0], round(self.ni.smpl_rate * settings.post_delay)))
#             frame = np.hstack([frame, delay])

#         if settings.pre_delay > 0:
#             delay = np.zeros((frame.shape[0], round(self.ni.smpl_rate * settings.pre_delay)))
#             frame = np.hstack([delay, frame])

#         return frame


class Brightfield:
    def __init__(self, ni:NIDAQ):
        self.flippers = Flippers()
        self.led_on = False
        self.flippers_up = False
        self.ni = ni
        self.led(False)
        self.flippers.brightfield(False)

    def toggle_led(self):
        self.led(not self.led_on)
        self.led_on = not self.led_on

    def toggle_flippers(self, up:bool = None):
        up = not self.flippers_up if up is None else up
        self.flippers.brightfield(up)
        self.flippers_up = up

    def led(self, on:bool = True, power: float = 1.):
        self.led_on = on
        power = power if on else 0
        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan("Dev1/ao6")
            task.write(power, auto_start=True)

    def one_frame(self, settings):
        led = make_pulse(self.ni, 0, 0.3, 0)
        return led


if __name__ == '__main__':
    import sys
    from PyQt5 import QtWidgets
    app = QtWidgets.QApplication(sys.argv)

    event_thread = EventThread()
    event_thread.start()

    ni = NIDAQ(event_thread)

    settings_view = SettingsView(event_thread)
    settings_view.show()

    sys.exit(app.exec_())

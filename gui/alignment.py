import nidaqmx
import nidaqmx.stream_writers
import numpy as np
# import hardware.FilterFlipper as FilterFlipper
import weakref
import matplotlib.pyplot as plt
from hardware._devices import NIController, DAQSettings, DAQDevice
from hardware.nidaq_components.settings import NIDAQSettings
from hardware.nidaq_components.devices import Camera, Galvo, Twitcher, LED, AOTF

GALVO_CENTER = -0.075
TWITCHER_CENTER = 5

def aotf(power:float = 10, transmit:bool = True):
    value = 10 if transmit else 0
    power = power if transmit else 0
    with nidaqmx.Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao3")
        task.ao_channels.add_ao_voltage_chan("Dev1/ao4")
        task.write([value, power], auto_start=True)


def center_mirrors():
    # 221121: Changed default from -0.3 to 0.075
    with nidaqmx.Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(GALVO_CENTER, auto_start=True)
    with nidaqmx.Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao7")
        task.write(TWITCHER_CENTER, auto_start=True)

def center_galvo(pos: float = GALVO_CENTER):
    with nidaqmx.Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
        task.write(pos, auto_start=True)

def center_twitchers(pos: float = TWITCHER_CENTER):
    with nidaqmx.Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao7")
        task.write(pos, auto_start=True)

def led_on(power=10):
    with nidaqmx.Task() as task:
        task.ao_channels.add_ao_voltage_chan("Dev1/ao6")
        task.write(power, auto_start=True)

# def brightfield(on:bool = True):
#     power = 0.3 if on else 0
#     aotf(not on)
#     led_on(power)
#     FilterFlipper.brightfield(on)


def makePulse(start, end, offset):
    SamplingRate = 500
    SweepsPerFrame = 1
    noPoints = SamplingRate*SweepsPerFrame
    DutyCycle=10/noPoints
    up = np.ones(round(DutyCycle*noPoints))*start
    down = np.ones(noPoints-round(DutyCycle*noPoints))*end
    pulse = np.concatenate((up,down)) + offset
    return pulse


class NI(NIController):
    def __init__(self, settings: NIDAQSettings = NIDAQSettings(cycle_time=100,sampling_rate=8400, camera_readout_time=0.0229),
                 camera: DAQDevice = Camera, galvo: DAQDevice = Galvo,
                 twitcher: DAQDevice = Twitcher, led: DAQDevice = LED, aotf: DAQDevice = AOTF):
        self.settings = settings
        self.camera = camera(settings)
        self.galvo = galvo(settings)
        self.twitcher = twitcher(settings)
        self.led = led(settings)
        self.aotf = aotf(settings)
        self.task_name = "isim_align_v0_10"
        self.channels = ['Dev1/ao0', 'Dev1/ao2','Dev1/ao7','Dev1/ao6', 'Dev1/ao3', 'Dev1/ao4', 'Dev1/ao5'] #galvo, camera, twitcher

        self.stop_data = np.asarray([[self.galvo.offset, 0, (-self.twitcher.amp) + self.twitcher.offset, 0,
                                      0, self.aotf.power_488/10, 0]]).astype(np.float64).transpose()
        self.stop_data = np.tile(self.stop_data, self.one_sequence().shape[1])
        return super()._init()

    def one_sequence(self):
        galvo_frame = self.galvo.one_frame(self.settings)
        # galvo_frame = (self.twitcher.one_frame(self.settings)-5)*0.1
        # galvo_frame = np.ones(galvo_frame.shape)*self.galvo.offset_0
        camera_data = self.camera.one_frame(self.settings)
        twitch_data = self.twitcher.one_frame(self.settings)
        led_data = self.led.one_frame(self.settings)
        # twitch_data = np.ones(twitch_data.shape)*5
        aotf_data = self.aotf.one_frame(self.settings)
        self.daq_data = np.vstack((galvo_frame, camera_data, twitch_data, led_data, aotf_data))
        no_frames = 5
        self.daq_data = np.tile(self.daq_data, no_frames)
        print(self.daq_data.shape)
        return self.daq_data

    def cleanup(self):
        super().cleanup()
        center_mirrors()



# This does not work as we can't have multiple task running on the same card. There is only one
# sample clock on this card, so different sampling_rates wouldn't work anyways.
# class Twitch_Control(NIController):
#     def __init__(self, settings: NIDAQSettings = NIDAQSettings(sampling_rate = 5000)):
#         self.settings = settings
#         self.twitcher = Twitcher(settings)
#         self.task_name = "isim_twitch_align"
#         self.channels = ['Dev1/ao6']

#         self.stop_data = np.zeros((1,5000)).astype(np.float64)
#         return super()._init()

#     def one_sequence(self):
#         frame = self.twitcher.one_frame()
#         self.daq_data = np.asarray(frame)
#         no_frames = 5
#         self.daq_data = np.tile(self.daq_data, no_frames)
#         print(self.daq_data.shape)
#         return self.daq_data




# class Galvo():

#     def __init__(self, core = Core(), studio = Studio()):
#         self.task = None
#         self.amp_0 = 0.265

#         sampling_rate = 500
#         cycle_time = 100


#         frame_rate = 1/(cycle_time/1000)
#         self.smpl_rate = round(sampling_rate*frame_rate)
#         self.parking_voltage = -4

#         self.offset_0= -0.3

#         self.core = core
#         self.studio = studio
#         # Get resources ready
#         system = nidaqmx.system.System.local()
#         system.devices[0].reset_device()

#         self.camera = self.Camera(self, core, cycle_time)
#         self.init_task()

#     def init_task(self):

#         try:
#             print("Closing task")
#             self.task.stop()
#             self.task.close()
#         except:
#             print("No task to stop")
#         self.task =  nidaqmx.Task()
#         self.task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
#         self.task.ao_channels.add_ao_voltage_chan('Dev1/ao2')

#         self.daq_data = self.one_frame()


#         self.task.timing.cfg_samp_clk_timing(rate= self.smpl_rate,
#                                             sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
#                                             samps_per_chan=self.daq_data.shape[1])
#         self.task.out_stream.regen_mode = nidaqmx.constants.RegenerationMode.DONT_ALLOW_REGENERATION
#         self.stream = nidaqmx.stream_writers.AnalogMultiChannelWriter( self.task.out_stream,
#                                                                         auto_start=False)
#         self.stream.write_many_sample(self.daq_data)
#         self.task.register_every_n_samples_transferred_from_buffer_event(self.daq_data.shape[1]//2,
#                                                                         self.get_new_data)

#     def add_delays(self, frame, pre_delay = 0, post_delay = 0):
#         if post_delay > 0:
#             delay = np.ones(round(self.smpl_rate * post_delay)) * self.parking_voltage
#             frame = np.hstack([frame, delay])
#         if pre_delay > 0:
#             delay = np.ones(round(self.smpl_rate * pre_delay)) * self.parking_voltage
#             frame = np.hstack([delay, frame])
#         return frame

#     def get_new_data(self, task_handle, every_n_samples_event_type, number_of_samples, callback_data):
#         self.stream.write_many_sample(self.daq_data)
#         return 0

#     def plot(self):
#         plt.plot(self.daq_data[0, :])
#         plt.plot(self.daq_data[1, :])
#         plt.show()

#     def one_frame(self):
#         # Add the 10 ms in the waiting position

#         galvo_frame = self.galvo_frame()
#         galvo_frame = self.add_delays(galvo_frame)
#         camera_data = self.camera.one_frame()
#         self.daq_data = np.vstack((galvo_frame, camera_data))
#         no_frames = 10
#         self.daq_data = np.tile(self.daq_data, no_frames)
#         return self.daq_data

#     def galvo_frame(self, old=False):
#         readout_time = self.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#         readout_time = float(readout_time)*1E-9  # in seconds
#         print("Galvo readout: ", readout_time)
#         sampling_rate = 500
#         n_points = sampling_rate - round(self.smpl_rate*readout_time)
#         amp_0 = self.amp_0
#         if old:
#             down1 = np.linspace(0,-amp_0,round(n_points/(4)))
#             up = np.linspace(-amp_0,amp_0,round(n_points/(2)))
#             down2 = np.linspace(amp_0,0,round(n_points) -
#                                 round(n_points/(4)) -
#                                 round(n_points/(2)))

#             frame = np.concatenate((down1, up, down2))
#         else:
#             # This should take the 100 ms actual exposure time
#             frame = np.linspace(amp_0, -amp_0, n_points) + self.offset_0
#         readout_delay = np.ones(round(self.smpl_rate * readout_time)) * self.parking_voltage
#         frame = np.hstack([readout_delay, frame, readout_delay])
#         return frame

#     def swivel(self):
#         self.camera.adjust_exposure()
#         try:
#             self.task.start()
#         except:
#             self.init_task()
#             self.task.start()

#     def stop(self):
#         self.task.stop()
#         self.camera.reset_exposure()

#     def change_amp(self, amp=0.75, old=False):
#         self.amp_0 = amp
#         self.daq_data = self.one_frame()

#     def center(self,pos=-0.15):
#         self.task.close()
#         with nidaqmx.Task() as task:
#             task.ao_channels.add_ao_voltage_chan("Dev1/ao0")
#             task.write(pos, auto_start=True)


#     class Camera:
#         def __init__(self, galvo, core, exposure=100):
#             self.pulse_voltage = 5
#             self.galvo = galvo
#             self.core = core
#             self.exposure = exposure

#         def one_frame(self):
#             camera_frame = makePulse(self.pulse_voltage, 0, 0)
#             camera_frame = self.add_readout(camera_frame)
#             camera_frame = self.add_delays(camera_frame)
#             return camera_frame

#         def add_delays(self, frame, pre_delay = 0, post_delay=0):
#             if post_delay > 0:
#                 delay = np.zeros(round(self.galvo.smpl_rate * post_delay))
#                 frame = np.hstack([frame, delay])
#             if pre_delay > 0:
#                 delay = np.zeros(round(self.galvo.smpl_rate * pre_delay))
#                 frame = np.hstack([delay, frame])
#             return frame

#         def add_readout(self, frame):
#             readout_time = self.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#             readout_time = float(readout_time)*1E-9  # in seconds
#             print("Camera readout: ", readout_time)
#             readout_delay = np.zeros(round(self.galvo.smpl_rate * readout_time))
#             frame = np.hstack([frame, readout_delay])
#             return frame

#         def adjust_exposure(self):
#             readout_time = self.core.get_property("PrimeB_Camera", "Timing-ReadoutTimeNs")
#             readout_time = float(readout_time)*1E-6  # in milliseconds
#             exposure_set = float(self.core.get_property("PrimeB_Camera", "Exposure"))
#             self.core.set_property("PrimeB_Camera", "Exposure", exposure_set + readout_time)
#             self.core.set_exposure(exposure_set + readout_time)
#             print("Exposure set to ",  exposure_set + readout_time)

#         def reset_exposure(self):
#             self.core.set_property("PrimeB_Camera", "Exposure", self.exposure)
#             self.core.set_exposure(self.exposure)
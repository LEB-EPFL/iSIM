import nidaqmx
import nidaqmx.stream_writers
import numpy as np

def sine():
    # Define the parameters
    frequency = 3.1  # Frequency of the sine wave in Hz
    duration = 1  # Duration in seconds
    sample_rate = 100  # Sampling rate in samples per second
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    sine_wave = np.sin(2 * np.pi * frequency * t) * 5 + 5
    sine_wave = np.append(sine_wave, np.zeros(1))
    return sine_wave

def change_led(LED: bool, task: nidaqmx.Task):
    LED = not LED
    data = np.zeros(101) if not LED else sine()
    print(len(data))
    task.write(data)



try:
    LED = True
    task = nidaqmx.Task()
    task.ao_channels.add_ao_voltage_chan('Dev1/ao6')
    task.timing.cfg_samp_clk_timing(rate=100, sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)
    task.start()
    while True:
        # Use the input function to wait for Enter key press
        user_input = input("Press Enter to continue...")
        LED = not LED
        # Check if the user_input is an empty string (Enter key was pressed)
        if user_input == "":
            change_led(LED, task)
            continue  # Continue the loop if Enter key is pressed
        else:
            print("You didn't press Enter. Please press Enter to continue.")
except KeyboardInterrupt:
    task.write(0)
    task.close()
    print("\nLoop interrupted by user.")
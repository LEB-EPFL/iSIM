import zarr
import multiprocessing as mp

def write_data(arr, synchronizer):
    # Write data to the synchronized array
    with synchronizer:
        arr[0] = 42

def read_data(arr, synchronizer):
    # Read data from the synchronized array
    with synchronizer:
        data = arr[0]
    print("Data read from synchronized array:", data)

if __name__ == '__main__':
    # Create a zarr array with a ProcessSynchronizer
    synchronizer = zarr.ProcessSynchronizer()
    arr = zarr.zeros((1,), dtype=int, synchronizer=synchronizer)

    # Start a process to write data to the array
    writer_process = mp.Process(target=write_data, args=(arr, synchronizer))
    writer_process.start()

    # Start a process to read data from the array
    reader_process = mp.Process(target=read_data, args=(arr, synchronizer))
    reader_process.start()

    # Wait for both processes to finish
    writer_process.join()
    reader_process.join()

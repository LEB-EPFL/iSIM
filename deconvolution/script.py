#!‪C:\Internal\.envs\decon_310\Scripts\python.exe

import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "0"

my_version = "20240416_2"

os.system("C:/Internal/.envs/decon_310/Scripts/activate")
os.system("cd C:/Internal/deconvolution")
my_version = "main" if my_version == "latest" else my_version
os.system(f"git checkout {my_version}")

from prepare import test_versioning
import time

test_versioning()
time.sleep(3)
# import tensorflow

# gpus = tensorflow.config.list_physical_devices('GPU')
# for gpu in gpus:
#     tensorflow.config.experimental.set_memory_growth(gpu, True)



# from pathlib import Path
# from prepare import get_filter_zone_ver_stripes, prepare_one_slice
# import cuda_decon

# # Import
# # folder = "Z:/iSIMstorage/Users/Willi/decon_test_Tatjana/"
# # file = r"\\lebnas1\microsc125\iSIMstorage\Users\Willi\decon_test_Tatjana\Cell_1\original.tif"
# # cuda_decon.decon_one_frame(file, {'background': 'median'})
# # folder = r"\\lebnas1.epfl.ch\microsc125\iSIMstorage\Users\Tatjana\2022\220302_MEFwt_MitotrG_S5"
# # folder = r"Z:\iSIMstorage\Users\Tatjana\2022\2207\220713"
# folder = r"W:\iSIMstorage\Users\Willi\20230201_u2os_presets"
# # folder = r"Z:/iSIMstorage/Users/Juan/230202_EDA-TrainingData/230202_U2OS_mtSG-TfamRFP_10"
# # folder = r"Y:\_Lab members\Christian_Z\cryo_CEMExM\data\230202_NHS_Christian"  # \230202_NHS_2N__3"

# # folder = r"W:\iSIMstorage\Users\Juan\230503_MEF_Opa1\Data"

# files = Path(folder).rglob('*.ome.tif')

# print(files)

# parameters = {
#     'background': "median",
# }
# # background      0-3: otsu with this scaling factor
# # background      > 3: fixed value
# # background 'median': median of each z-stack as bg

# for file in files:
#     if not 'decon' in file.name:
#         print(file.name)
#         print(file.as_posix())
#         cuda_decon.decon_ome_stack(file.as_posix(), params=parameters)


# files = [r'Z:\iSIMstorage\Users\Juan\DOX CP tests\Day2\Processed\Control_2_MMStack_Pos0.ome.tif']
# files = [r'\\lebnas1.epfl.ch\\microsc125\\iSIMstorage\\Users\\Juan\\DOX CP tests\\Day2']
# # For Juan
# import tifffile
# import xmltodict
# from tqdm import tqdm
# import numpy as np
# for file in files:
#     with tifffile.TiffFile(file) as tif:
#         data = tif.asarray()
#         imagej_metadata = tif.imagej_metadata
#         my_dict = xmltodict.parse(tif.ome_metadata, force_list={'Plane'})
#         size_t = int(my_dict['OME']['Image']["Pixels"]["@SizeT"])
#         size_c = int(my_dict['OME']['Image']["Pixels"]["@SizeC"])
#         size_z = int(my_dict['OME']['Image']["Pixels"]["@SizeZ"])

#     if size_z == 1:
#         data = np.expand_dims(data, 1)
#     if size_c == 1:
#         data = np.expand_dims(data, 2)

#     destripped = np.zeros(data.shape)
#     for timepoint in tqdm(range(size_t)):
#         data_t = data[timepoint, :, :, :, :]
#         for channel in range(size_c):
#             frame = data_t[0, channel, :, :]
#             destripe = prepare_one_slice(frame, background=100, filter_zone_source=get_filter_zone_ver_stripes)
#             destripped[timepoint, 0, channel, :, :] = destripe

#     try:
#         imagej_metadata['min'] = np.min(destripped)
#         imagej_metadata['max'] = np.max(destripped)
#         imagej_metadata['Ranges'] = (np.min(destripped), np.max(destripped))
#     except TypeError:
#         print("Could not set imagej_metadata")

#     out_file = os.path.basename(file).rsplit('.', 2)
#     out_file = out_file[0] + ".".join(["_destripped", *out_file[1:]])
#     with tifffile.TiffWriter(os.path.join(os.path.dirname(file), out_file), imagej=True) as tif:
#         tif.write(destripped.astype(np.uint16), metadata=imagej_metadata)





os.system("git checkout main")
""" Set your version or put latest """
MY_VERSION="latest"

""" This part should be in all scripts """
#! C:\Internal\.envs\decon_310\Scripts\python.exe
import os
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
from versioning import set_version_and_venv, reset_repo
set_version_and_venv(MY_VERSION)
from pathlib import Path
from prepare import get_filter_zone_ver_stripes
import cuda_decon
os.environ['CUDA_VISIBLE_DEVICES'] = "0"

""" Set the data to be deconvolved """
folder = r"X:/Scientific_projects/MMJ_CEZ/data/iSIM/20240422_IL-2_4d_test_mitotracker_red"
files = Path(folder).rglob('*.ome.tif*')

""" Settings """
parameters = {
    'background': "median",
    # 'destripe_zones': get_filter_zone_ver_stripes
}
# background      0-3: otsu with this scaling factor
# background      > 3: fixed value
# background 'median': median of each z-stack as bg

for file in files:
    if not 'decon' in file.name:
        print(file.name)
        print(file.as_posix())
        cuda_decon.decon_ome_stack(file.as_posix(), params=parameters)

""" For all scripts """
reset_repo()
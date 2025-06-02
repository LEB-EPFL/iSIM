# iSIM Control based in pymmcore-plus
This is the 'new' version of the control software for the iSIM microscope. It's based in pymmcore-plus with some custom components to enable the hardware sequenced control for the iSIM. Overall Structure is described in [Overview](./doc/strucutre_overview.md) with more details in [Structure](./doc/structure.md) and [Communications](./doc/output_comms.md).

# Controller
![controller functions](../docs/Controller.PNG)

# Installation
### Assumptions
- Windows PC
- Python 3.11.4 is installed

### Steps

1. Create a folder on the PC called C:\iSIM\.
1. Clone this repository into that folder
1. Generate a uv venv in C:\iSIM\iSIM\control
1. Activate the environment
1. Run uv sync in that folder
1. micro-manager has to be installed. The easiest is to use the CLI
    ```
    mmcore.exe included with pymmcore-plus.
    mmcore install -d C:\isim
    mmcore use C:\iSIM\Micro-Manager_2.0.3_20250523 #replace with used version
    You can use this to install a certain version (20250523 works when this is written)
          -r, --release TEXT    Release date. e.g. 20210201  \[default: latest-compatible]
    ```
1. Make a shortcut to run C:\iSIM\iSIM\control\main.ps1
1. For each user follow [add new user](../docs/new_user.md)


Logs are here:
C:\Users\~you~\AppData\Local\pymmcore-plus\pymmcore-plus\logs
Settings files per user are here:
C:\Users\~you~\.isim

To change the orientation of the image to match your preference for how the stage should work got to:
C:\Users\your_account\.isim\live_view.json
and adjust the settings there.

# Alignment
The alignment procedure has to be used from the old software [Alignment](../gui/README.md#alignment)
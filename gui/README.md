# iSIM Control

Python Control Interface for the iSIM at LEB-EPFL

## Installation

### Assumptions

- Windows PC
- Python 3.9.5 is installed

### Steps

1. Create a folder called on the PC called `C:\iSIM\`.
1. Install **Micro-Manager 2.0.1 20220523** into `C:\iSIM\Micro-Manager-2.0.2`.
1. Clone this repo and move the folder called `gui` to `C:\iSIM\isimgui` on the control PC.
1. Copy `MMStartup.bsh` from this repo to the Micro-Manager folder.
1. Install the `AcquireButtonHijack` and `PseudoChannels` Micro-Manager plugins from this repository by copying the .jar files from a GitHub release into `C:\iSIM\Micro-Manager-2.0.2\mmplugins`.
1. Install the `pymm-eventserver` Micro-Manager plugin from https://github.com/LEB-EPFL/pymm-eventserver by copying the .jar file into the same directory as the previous step.
1. Create a new Python virtual environment with the following command. Note the directory! `python -m venv C:\iSIM\isim_python_env`.
1. Activate the virtual environment in a Powershell console: `C:\iSIM\isim_python_env\Scripts\Activate.ps1`.
1. Move into the cloned repository: `Set-Location C:\iSIM\isimgui`.
1. Install the control software: `pip install .`
1. Create a shortcut to `C:\iSIM\Micro-Manager-2.0.2\ImageJ.exe` on the Desktop if it doesn't already exist.

## Alignment

This repository contains a GUI for aligning the microlenses and pinhole array of the iSIM. It displays regions from a live feed of the illumination spots overlaid with guidelines and spot centers. The goal of the alignment is to bring the centers of the spots to coincide with the guidelines in all regions of the field of view.

To launch the alignment tool, first start Micro-Manager. In the `pymm-eventserver` plugin GUI window, ensure that the `Live Mode Events` checkbox is checked.

Next, start the alignment GUI from this directory with the following command:

```console
py main.py alignment
```

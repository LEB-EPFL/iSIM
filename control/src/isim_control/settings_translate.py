from isim_control.settings import iSIMSettings
from pymmcore_plus import CMMCorePlus
from useq import MDASequence
import json
from pathlib import Path

def add_settings_from_core(mmcore: CMMCorePlus, settings: iSIMSettings):
    settings['camera']['name'] = mmcore.getCameraDevice()
    readout = mmcore.getProperty(settings['camera']['name'], "Timing-ReadoutTimeNs")
    settings['camera']['readout_time'] = float(readout)/1e9
    settings['camera']['exposure_time'] = float(mmcore.getExposure())/1000
    return settings


def useq_from_settings(settings: iSIMSettings):
    print(settings['acquisition'])
    return MDASequence(**settings['acquisition'])


def acquisition_settings_from_useq(settings: iSIMSettings, seq: MDASequence):
    settings['acquisition'] = seq.model_dump()
    settings['exposure_time'] = settings['acquisition']['channels'][0]['exposure']
    settings.calculate_ni_settings()
    return settings

def save_settings(settings: iSIMSettings):
    path = Path.home() / ".isim" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as file:
        json.dump(settings, file)

def load_settings():
    try:
        path = Path.home() / ".isim" / "settings.json"
        with path.open("r") as file:
            settings_dict = json.load(file)
        if settings_dict == {}:
            raise FileNotFoundError
        settings = iSIMSettings(full_settings=settings_dict)
    except (FileNotFoundError, TypeError, AttributeError):
        print("New iSIMSettings for this user")
        settings = iSIMSettings()
    return settings
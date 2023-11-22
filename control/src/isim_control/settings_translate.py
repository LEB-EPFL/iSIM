from isim_control.settings import iSIMSettings
from pymmcore_plus import CMMCorePlus
from useq import MDASequence
import json
from pathlib import Path
from datetime import timedelta

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

def save_settings(settings: iSIMSettings|dict, filename: str = "settings"):
    # The interval in the time_plan settings is a timedelta, which is not JSON serializable
    try:
        settings['acquisition']['time_plan']['interval'] = \
            settings['acquisition']['time_plan']['interval'].seconds
    except:
        pass
    path = Path.home() / ".isim" / f"{filename}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as file:
        file.write(json.dumps(settings, indent=2))


def load_settings(filename: str = "settings"):
    try:
        path = Path.home() / ".isim" / f"{filename}.json"
        with path.open("r") as file:
            settings_dict = json.load(file)
        if settings_dict == {}:
            raise FileNotFoundError
        if filename == "settings":
            settings_dict['acquisition']['time_plan']['interval'] = \
                timedelta(seconds=settings_dict['acquisition']['time_plan']['interval'])
            settings = iSIMSettings(full_settings=settings_dict)
        else:
            settings = settings_dict
    except (FileNotFoundError, TypeError, AttributeError, json.decoder.JSONDecodeError) as e:
        import traceback
        print(traceback.format_exc())
        print("New iSIMSettings for this user")
        settings = iSIMSettings()
    return settings
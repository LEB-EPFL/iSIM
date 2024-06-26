import os
import sys

def set_version_and_venv(version: str = "latest", venv: str|None = None, set_user=True):
    if venv is None:
        venv = "C:/Internal/.envs/decon_310"
    os.environ['VIRTUAL_ENV'] = venv  # optional: to include the VIRTUAL_ENV variable
    sys.path.append(os.path.join(venv, 'lib', 'site-packages'))

    MY_VERSION = "main" if version == "latest" else version
    # This makes problems for a different user
    if set_user:
        os.system('git config --global user.name "LEB user"')
        os.system('git config --global user.email user@tesladesk.com')
    os.system(f"git config advice.detachedHead false")
    os.system(f"git stage --all")
    os.system(f"git commit -m automatic")
    os.system(f"git checkout {MY_VERSION}")

def reset_repo():
    os.system("git checkout main")
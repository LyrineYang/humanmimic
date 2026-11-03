"""Load the project-local corrected sensor; never fall back to wrong-sign data."""
import hashlib
import json
import os
from pathlib import Path
import mujoco

PLUGIN='humanmimic.sensor.touch_grid'
_loaded=None

def load_sensor():
    global _loaded
    if _loaded is not None:return _loaded
    directory=Path(os.environ['R4_DATA_ROOT'])/'native_plugins/touch_grid-3.2.7-v1'
    metadata=json.loads((directory/'manifest.json').read_text())
    library=directory/'libhumanmimic_touch_grid.so'
    if metadata['mujoco_version']!=mujoco.__version__ or metadata['plugin']!=PLUGIN:
        raise ValueError('R4 native sensor version mismatch')
    if hashlib.sha256(library.read_bytes()).hexdigest()!=metadata['library_sha256']:
        raise ValueError('R4 native sensor binary changed; rebuild and revalidate')
    mujoco.mj_loadPluginLibrary(str(library))
    _loaded=metadata
    return metadata

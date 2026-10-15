"""An absent real vendor constructor cannot be enabled by a receipt switch."""
import hashlib
import json
from pathlib import Path

def require_constructor():
    raise RuntimeError('MediaPipe FaceMesh managed constructor source unsupported: exact MediaPipe task buffer and old-solutions bundle definitions/resources required; owner GERALD')

def selected_construction():
    selected = json.loads(Path(__file__).with_name('asset-selection.json').read_text())
    # Even an approved flag cannot bypass a physically missing implementation.
    require_constructor()
    return selected

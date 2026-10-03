# LinkModeToggle – minimal server side stub so ComfyUI serves /web
# Place in: D:\AI\ComfyUI\custom_nodes\LinkModeToggle\__init__.py

__version__ = '0.1.1'
# ComfyUI loads this file and, seeing WEB_DIRECTORY, mounts /web automatically.
WEB_DIRECTORY = "./web"

import sys

def color_print(text, color_code="36"):  # 36 = cyan
    sys.stdout.write(f"\033[{color_code}m{text}\033[0m\n")

color_print("[ComfyUI-LinkModeToggle] v0.1.0 loaded ✓", "96")  # 96 = bright cyan

# No Python nodes here; purely a web extension.
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}



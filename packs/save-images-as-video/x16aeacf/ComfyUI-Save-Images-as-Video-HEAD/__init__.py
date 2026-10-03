import os
from .nodes import NODE_CLASS_MAPPINGS as FFMPEG_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS as FFMPEG_DISPLAY_MAPPINGS
from .node_logger import log_node_info, log_node_success, log_node_error, log_node_warning, log_node_debug
from .ffmpeg_path_resolver import initialize_ffmpeg_path_and_log

NODE_CLASS_MAPPINGS = {
    **FFMPEG_MAPPINGS,
    # **OTHER_MAPPINGS, # Розкоментуйте та додайте інші, якщо є
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **FFMPEG_DISPLAY_MAPPINGS,
    # **OTHER_DISPLAY_MAPPINGS, # Розкоментуйте та додайте інші, якщо є
}

# WEB_DIRECTORY = "./js" # Вказує на папку js

# __all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

# Визначаємо шлях до директорії пакету
PACKAGE_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
INIT_LOG_PREFIX = "San4itosInit" 

initialize_ffmpeg_path_and_log(PACKAGE_DIRECTORY)

log_node_info(INIT_LOG_PREFIX, "*** Custom Nodes from ComfyUI-san4itos Initialized ***")

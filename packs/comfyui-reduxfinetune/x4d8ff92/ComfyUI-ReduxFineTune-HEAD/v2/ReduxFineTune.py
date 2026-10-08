from ._secure_nodes import ReduxFineTune, ReduxFineTuneAdvanced
from ._schema import DISPLAY
NODE_CLASS_MAPPINGS={'ReduxFineTune':ReduxFineTune,'ReduxFineTuneAdvanced':ReduxFineTuneAdvanced}
NODE_DISPLAY_NAME_MAPPINGS={key:DISPLAY[key] for key in NODE_CLASS_MAPPINGS}

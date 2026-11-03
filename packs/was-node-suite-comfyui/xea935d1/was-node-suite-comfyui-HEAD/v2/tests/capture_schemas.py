"""Capture every declared node's schema from the pristine WAS fork (gate container only; no pack code runs on
the host). The original's own WAS_BLOCK_AUTO_INSTALL switch (WAS_Node_Suite.py:346) blocks its pip installs.
Writes /results/schemas.json: per NODE_CLASS_MAPPINGS key, INPUT_TYPES() and the class attributes the executor
and the frontend read."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import sys

sys.path[:0] = ['/core']
if os.path.isdir('/deps'):
    sys.path.insert(0, '/deps')
os.environ['WAS_BLOCK_AUTO_INSTALL'] = '1'
sys.argv = ['main.py', '--cpu']
import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
import folder_paths  # noqa: E402

WORK = Path('/tmp/amy-was-capture')
for name, setter in (('output', folder_paths.set_output_directory), ('temp', folder_paths.set_temp_directory),
                     ('input', folder_paths.set_input_directory)):
    (WORK / name).mkdir(parents=True, exist_ok=True)
    setter(str(WORK / name))
(WORK / 'user').mkdir(parents=True, exist_ok=True)
folder_paths.set_user_directory(str(WORK / 'user'))  # WAS writes user/default/was-node-suite at import
os.chdir(WORK)
import nodes as core_nodes  # noqa: E402

pack_dir = WORK / 'custom_nodes' / 'was-node-suite-comfyui'
shutil.copytree('/pack', pack_dir, ignore=shutil.ignore_patterns('v2'))
loaded = asyncio.run(core_nodes.load_custom_node(str(pack_dir), ignore=set(), module_parent='custom_nodes'))
module = sys.modules[str(pack_dir).replace('.', '_x_')]
mapping = module.NODE_CLASS_MAPPINGS


def plain(value):
    return json.loads(json.dumps(value, default=lambda v: getattr(v, 'value', str(v))))


rows = {}
for key, cls in mapping.items():
    row = {'class': cls.__name__, 'module': cls.__module__.rsplit('.', 1)[-1]}
    try:
        row['input_types'] = plain(cls.INPUT_TYPES())
    except Exception as error:
        row['input_types_error'] = f'{type(error).__name__}: {error}'
    for attr in ('RETURN_TYPES', 'RETURN_NAMES', 'OUTPUT_NODE', 'CATEGORY', 'FUNCTION', 'INPUT_IS_LIST',
                 'OUTPUT_IS_LIST', 'DESCRIPTION', 'OUTPUT_TOOLTIPS', 'DEPRECATED', 'EXPERIMENTAL'):
        if hasattr(cls, attr):
            row[attr] = plain(getattr(cls, attr))
    row['has_IS_CHANGED'] = hasattr(cls, 'IS_CHANGED')
    row['has_VALIDATE_INPUTS'] = hasattr(cls, 'VALIDATE_INPUTS')
    rows[key] = row
report = {'loaded': bool(loaded), 'count': len(rows),
          'display_names': plain(getattr(module, 'NODE_DISPLAY_NAME_MAPPINGS', None)),
          'web_directory': getattr(module, 'WEB_DIRECTORY', None), 'nodes': rows}
Path('/results/schemas.json').write_text(json.dumps(report, indent=1) + '\n')
print(json.dumps({'loaded': report['loaded'], 'count': report['count'],
                  'errors': {k: v['input_types_error'] for k, v in rows.items() if 'input_types_error' in v}}))

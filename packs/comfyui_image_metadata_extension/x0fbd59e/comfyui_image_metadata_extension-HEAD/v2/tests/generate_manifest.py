"""Generate v2/secure-nodes.json with the real encoder (gate container only; LANE-SPEC rule 4).

run_in_gate.sh <pack root> <v2/tests> <results> generate_manifest.py
Writes /results/secure-nodes.json; also checks it against the committed v2/secure-nodes.json when present.
"""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import sys

sys.path[:0] = ['/core', '/overlay']
sys.argv = ['generate_manifest', '--cpu']
import comfy.options  # noqa: E402
comfy.options.enable_args_parsing()
from comfy_api.latest import io  # noqa: E402
from comfy_secure_nodes.packmanifest import (FORMAT, encode_required_weights, encode_schema,  # noqa: E402
                                             encode_validation_inputs)
from comfy_secure_nodes.packruntime import manifest_declaration  # noqa: E402

V2 = Path('/pack/v2')
NAME = '_amy_meta_v2_manifest'
spec = importlib.util.spec_from_file_location(NAME, V2 / '__init__.py', submodule_search_locations=[str(V2)])
package = importlib.util.module_from_spec(spec)
sys.modules[NAME] = package
spec.loader.exec_module(package)
classes = asyncio.run(asyncio.run(package.comfy_entrypoint()).get_node_list())
rows = {}
for cls in classes:
    schema = copy.deepcopy(cls.GET_SCHEMA())
    module_file = Path(sys.modules[cls.__module__].__file__).resolve()
    relative = module_file.relative_to(V2.resolve())
    relative = relative.parent if relative.name == '__init__.py' else relative.with_suffix('')
    methods = {m: getattr(cls, m).__func__ is not getattr(io.ComfyNode, m).__func__
               for m in ('validate_inputs', 'fingerprint_inputs', 'check_lazy_status')}
    row = {'module': '.'.join(relative.parts), 'class': cls.__name__, 'sdk_refs': bool(getattr(cls, 'SDK_REFS', False)),
           'permissions': list(getattr(cls, 'SDK_PERMISSIONS', ()) or ()), 'methods': methods,
           'schema': encode_schema(schema)}
    if methods['validate_inputs']:
        row['validation_inputs'] = encode_validation_inputs(cls)
    weights = encode_required_weights(cls)
    if weights:
        row['required_weights'] = weights
    rows[schema.node_id] = row
manifest = {'format': FORMAT, 'runtime': manifest_declaration(V2), 'nodes': rows, 'web_directory': None,
            'frontend_permissions': []}
text = json.dumps(manifest, indent=2, sort_keys=True) + '\n'
Path('/results/secure-nodes.json').write_text(text)
committed = V2 / 'secure-nodes.json'
status = {'nodes': sorted(rows), 'committed_present': committed.exists(),
          'committed_equal': committed.exists() and committed.read_text() == text}
Path('/results/manifest-check.json').write_text(json.dumps(status, indent=2) + '\n')
print(json.dumps(status))

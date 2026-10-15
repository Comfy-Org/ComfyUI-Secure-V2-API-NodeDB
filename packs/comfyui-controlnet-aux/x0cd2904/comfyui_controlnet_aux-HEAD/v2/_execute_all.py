"""ExecuteAll is held at its proven public graph boundary.

R98's literal original Core planner is preserved in its immutable source
packet. It cannot be imported or returned directly by the canonical guest.
No host-private import, unsigned graph, missing child or changed batch math
is used to disguise the current public contract gap.
"""
import hashlib,json
from pathlib import Path
raw=Path(__file__).with_name('_execute_all_options.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='a242c01b514550ff63896d12d0e8b21e532125cb1988c5f0c2a15386b5a31b48'
PREPROCESSOR_OPTIONS=json.loads(raw)

def expand_all(image, resolution=512):
    raise RuntimeError(
        'ExecuteAllControlNetPreprocessors: exact original47-child/140-node '
        'expansion is unqualified: public graph.expand_nodes permits1..128 '
        'nodes, core ImageBatch is not an allowed converted-pack target, '
        'and raw guest graphs are not host-issued expansion tickets. '
        'A bounded pack-local batch/staging implementation and exact graph '
        'permissions/namespace require separate source and execution review.')

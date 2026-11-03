"""Guest-side stand-in for comfy_execution.utils.get_executing_context (Secure Nodes V2).

Upstream's DiT and VAE loader nodes read get_executing_context().node_id into their config dict.
A guest cannot import comfy_execution. The secure node asks the SDK for the executing node id
(ctx.graph.current_node_id()) and runs upstream's execute inside executing(node_id). This is a
pack-local helper, not a stub of the host module.
"""

import contextlib
import contextvars
from types import SimpleNamespace

_CURRENT = contextvars.ContextVar("seedvr2_executing_context", default=None)


@contextlib.contextmanager
def executing(node_id):
    token = _CURRENT.set(SimpleNamespace(node_id=node_id))
    try:
        yield
    finally:
        _CURRENT.reset(token)


def get_executing_context():
    # Like upstream: None outside an execution, so `.node_id` fails the same way.
    return _CURRENT.get()

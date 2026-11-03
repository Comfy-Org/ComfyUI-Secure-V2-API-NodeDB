"""Local dependency refusals at the original helper call boundary."""
from contextvars import ContextVar

node_scope = ContextVar('layerstyle_node_id')
probe_scope = ContextVar('layerstyle_validation_probe', default=False)


class DependencyRefusal(RuntimeError):
    pass


def refuse(purpose):
    raise DependencyRefusal(f'comfyui_layerstyle/{node_scope.get()} {purpose}')

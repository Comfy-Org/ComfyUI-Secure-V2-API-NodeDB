"""Load only this converted pack's fixed implementation modules."""
import importlib
_MODULES=frozenset({'_handlers','_impl_main','_impl_legacy','_impl_dev'})
def load(name):
    if name not in _MODULES:raise ValueError('Unknown pack implementation module')
    return importlib.import_module('.'+name,__package__)

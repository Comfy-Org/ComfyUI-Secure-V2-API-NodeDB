"""Per-execution RNG scope; every pinned helper reseed remains observable."""
import contextvars
import random as _stdlib_random
from contextlib import contextmanager
_current=contextvars.ContextVar('ebu_execution_random')
class LocalRandom:
    def __getattr__(self,name):
        return getattr(_current.get(),name)
random=LocalRandom()
@contextmanager
def scope():
    token=_current.set(_stdlib_random.Random())
    try:
        yield
    finally:
        _current.reset(token)

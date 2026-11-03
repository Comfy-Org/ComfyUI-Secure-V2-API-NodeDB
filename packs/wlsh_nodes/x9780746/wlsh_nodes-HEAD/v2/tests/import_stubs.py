"""TEST ADAPTATION (labelled): import stubs for the original's heavy dependencies that the gate image lacks.

The original package imports modules at package import that the gate image may lack (for RES4LYF:
matplotlib, cv2, pywt, opensimplex). The tests only exercise the converted nodes,
whose code paths use none of these. A stub satisfies the import; any real use raises a RuntimeError naming the
stubbed attribute, so a stub can never silently stand in for a dependency in a comparison.

The one exception is a call the original makes while importing, named in ``noop_calls``. For RES4LYF that is
``matplotlib.use('Agg')`` (helper_sigma_preview_image_preproc.py:19), a backend choice for its preview plots. A
named no-op call returns None; every other use still raises.

    import import_stubs; import_stubs.install(["cv2", ...], noop_calls=["matplotlib.use"])   # before the original
"""
import importlib.abc
import importlib.machinery
import sys
import types

NOOP_CALLS = set()


class _Missing:
    def __init__(self, path):
        self._path = path

    def __getattr__(self, name):
        return _Missing(f"{self._path}.{name}")

    def __call__(self, *args, **kwargs):
        if self._path in NOOP_CALLS:
            return None
        raise RuntimeError(f"stubbed dependency used: {self._path} (test adaptation; not available in the gate)")

    def __mro_entries__(self, bases):  # allow `class X(stub.Base)` at import time
        return (object,)

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return False


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _Missing(f"{self.__name__}.{name}")


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, roots):
        self.roots = set(roots)

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in self.roots:
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        module = _StubModule(spec.name)
        module.__path__ = []
        module.__stubbed__ = True
        return module

    def exec_module(self, module):
        return None


STUBBED = []


def install(roots, noop_calls=()):
    missing = []
    for root in roots:
        try:
            __import__(root)
        except Exception:  # noqa: BLE001  (only stub what is genuinely absent)
            missing.append(root)
    if missing:
        NOOP_CALLS.update(call for call in noop_calls if call.split(".")[0] in missing)
        sys.meta_path.insert(0, _StubFinder(missing))
        STUBBED.extend(missing)
    return list(missing)

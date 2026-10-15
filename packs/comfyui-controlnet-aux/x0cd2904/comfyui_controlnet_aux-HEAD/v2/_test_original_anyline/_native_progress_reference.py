"""Reference-only progress counter; model pixels and RNG do not depend on UI reporting.

The genuine native method reports three progress updates. The parity oracle
retains their order using this local counter because secure guests do not import
host Comfy modules. No host module is stubbed, imported, or placed in sys.modules;
production progress handling is unchanged and reference UI progress is not qualified.
"""
class ProgressBar:
    def __init__(self,total):
        self.total=total
        self.value=0
    def update(self,value):
        self.value+=value

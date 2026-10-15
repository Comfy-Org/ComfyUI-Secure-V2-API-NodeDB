"""Explicit CPU runtime adaptations for the retained full Wan VAE math.

No Comfy modules are installed or impersonated in the converted guest. Native
disable_weight_init.Conv3d uses the ordinary Torch Conv3d CPU forward when
weights are resident and unpatched; this class retains that path and its
uninitialized construction before strict complete state loading.
"""
import logging
import torch

device = torch.device('cpu')
log = logging.getLogger(__name__)


class NoInitConv3d(torch.nn.Conv3d):
    def reset_parameters(self):
        return None


class ProgressBar:
    """Keep synchronous model progress visible through ordinary guest logging."""
    def __init__(self, total):
        self.total = total
        self.current = 0

    def update(self, amount):
        self.update_absolute(self.current + amount)

    def update_absolute(self, value, total=None):
        if total is not None:
            self.total = total
        self.current = value
        log.info('Wan VAE progress %s/%s', self.current, self.total)


def print_memory(device, process='Sampling'):
    # Exact original utility; CPU verbose behavior is deliberately not hidden.
    max_memory = torch.cuda.max_memory_allocated(device) / 1024**3
    max_reserved = torch.cuda.max_memory_reserved(device) / 1024**3
    log.info(f'[{process}] Max allocated memory: {max_memory=:.3f} GB')
    log.info(f'[{process}] Max reserved memory: {max_reserved=:.3f} GB')

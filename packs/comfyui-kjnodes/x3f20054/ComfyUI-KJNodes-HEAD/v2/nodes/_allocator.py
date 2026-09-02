from __future__ import annotations

from contextlib import contextmanager


class _AllocatorPolicy:
    ALLOWED = ("get_torch_device", "intermediate_device", "intermediate_dtype")

    def __init__(self):
        self._placement = None

    @contextmanager
    def bound_to(self, tensor):
        with self.bound_to_values(tensor.device, tensor.dtype):
            yield

    @contextmanager
    def bound_to_values(self, device, dtype):
        prior, self._placement = self._placement, (device, dtype)
        try:
            yield
        finally:
            self._placement = prior

    def _placement_values(self):
        if self._placement is None:
            raise RuntimeError(
                "tensor placement was requested outside a materialized input "
                "or an explicit pack-local allocation scope"
            )
        return self._placement

    def get_torch_device(self):
        return self._placement_values()[0]

    def intermediate_device(self):
        return self._placement_values()[0]

    def intermediate_dtype(self):
        return self._placement_values()[1]

    def __getattr__(self, name):
        raise AttributeError(
            f"{name} is host policy; this pack-local placement helper exposes "
            f"only {', '.join(self.ALLOWED)}"
        )


_allocator = _AllocatorPolicy()


def _allocating_like(tensor):
    return _allocator.bound_to(tensor)


def _allocating_on(device, dtype):
    return _allocator.bound_to_values(device, dtype)
